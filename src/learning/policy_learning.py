"""
Policy Learning and Improvement for Phase 2.

Provides:
- ingest_feedback(exceptionId, outcome, human_override)
- Pattern detection for recurring exceptions
- Success/failure pattern detection
- Policy suggestion generation (not auto-applied)

Safety:
- Suggestions only, never auto-edit tenant policies

Matches specification from phase2-mvp-issues.md Issue 35.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PolicyLearningError(Exception):
    """Raised when policy learning operations fail."""

    pass


class PolicySuggestion(BaseModel):
    """
    Policy suggestion generated from learning.
    
    Safety: These are suggestions only, never auto-applied.
    """

    suggestion_type: str = Field(..., description="Type of suggestion (e.g., 'severity_override', 'approval_rule')")
    description: str = Field(..., description="Human-readable description of suggestion")
    rationale: str = Field(..., description="Reason for suggestion")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in suggestion")
    suggested_change: dict[str, Any] = Field(..., description="Suggested policy change")


class PolicyLearning:
    """
    Policy learning from human corrections and overrides.
    
    Responsibilities:
    - Ingest feedback from exception processing
    - Detect recurring exceptions and patterns
    - Generate policy suggestions (not auto-applied)
    - Store learning artifacts per tenant
    """

    def __init__(self, storage_dir: str = "./runtime/learning"):
        """
        Initialize PolicyLearning.
        
        Args:
            storage_dir: Directory for storing learning artifacts
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory pattern tracking (per tenant)
        # Structure: {tenant_id: {pattern_key: pattern_data}}
        self._patterns: dict[str, dict[str, Any]] = defaultdict(dict)

    def ingest_feedback(
        self,
        tenant_id: str,
        exception_id: str,
        outcome: str,
        human_override: Optional[dict[str, Any]] = None,
        exception_type: Optional[str] = None,
        severity: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Ingest feedback for learning.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            outcome: Outcome string (e.g., "SUCCESS", "FAILED", "ESCALATED")
            human_override: Optional human override information
            exception_type: Optional exception type
            severity: Optional severity level
            context: Optional context from processing
            
        Raises:
            PolicyLearningError: If ingestion fails
        """
        try:
            # Build feedback record
            feedback_record = {
                "exceptionId": exception_id,
                "tenantId": tenant_id,
                "outcome": outcome,
                "exceptionType": exception_type,
                "severity": severity,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "humanOverride": human_override,
                "context": context or {},
            }
            
            # Persist to tenant-specific JSONL file
            self._persist_feedback(tenant_id, feedback_record)
            
            # Update pattern tracking
            self._update_patterns(tenant_id, feedback_record)
            
            logger.debug(
                f"Ingested feedback for exception {exception_id} "
                f"(tenant: {tenant_id}, outcome: {outcome})"
            )
            
        except Exception as e:
            raise PolicyLearningError(f"Failed to ingest feedback: {e}") from e

    def get_policy_suggestions(
        self,
        tenant_id: str,
        min_confidence: float = 0.7,
    ) -> list[PolicySuggestion]:
        """
        Get policy suggestions based on learned patterns.
        
        Args:
            tenant_id: Tenant identifier
            min_confidence: Minimum confidence threshold for suggestions
            
        Returns:
            List of policy suggestions (not auto-applied)
        """
        suggestions = []
        
        # Load patterns for tenant
        patterns = self._load_patterns(tenant_id)
        
        # Detect recurring exceptions
        recurring_suggestions = self._detect_recurring_exceptions(patterns, min_confidence)
        suggestions.extend(recurring_suggestions)
        
        # Detect success/failure patterns
        pattern_suggestions = self._detect_success_failure_patterns(patterns, min_confidence)
        suggestions.extend(pattern_suggestions)
        
        # Detect human override patterns
        override_suggestions = self._detect_human_override_patterns(patterns, min_confidence)
        suggestions.extend(override_suggestions)
        
        # Sort by confidence (highest first)
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        logger.info(
            f"Generated {len(suggestions)} policy suggestions for tenant {tenant_id} "
            f"(min_confidence: {min_confidence})"
        )
        
        return suggestions

    def _persist_feedback(self, tenant_id: str, feedback_record: dict[str, Any]) -> None:
        """
        Persist feedback record to tenant-specific JSONL file.
        
        Args:
            tenant_id: Tenant identifier
            feedback_record: Feedback record to persist
        """
        feedback_file = self.storage_dir / f"{tenant_id}.jsonl"
        
        # Append to JSONL file
        with open(feedback_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_record, default=str) + "\n")

    def _update_patterns(self, tenant_id: str, feedback_record: dict[str, Any]) -> None:
        """
        Update pattern tracking with new feedback.
        
        Args:
            tenant_id: Tenant identifier
            feedback_record: Feedback record
        """
        if tenant_id not in self._patterns:
            self._patterns[tenant_id] = {}
        
        # Track by exception type
        exception_type = feedback_record.get("exceptionType")
        if exception_type:
            pattern_key = f"exception_type:{exception_type}"
            if pattern_key not in self._patterns[tenant_id]:
                self._patterns[tenant_id][pattern_key] = {
                    "count": 0,
                    "outcomes": defaultdict(int),
                    "human_overrides": [],
                    "severities": defaultdict(int),
                }
            
            pattern = self._patterns[tenant_id][pattern_key]
            pattern["count"] += 1
            pattern["outcomes"][feedback_record["outcome"]] += 1
            
            if feedback_record.get("severity"):
                pattern["severities"][feedback_record["severity"]] += 1
            
            if feedback_record.get("humanOverride"):
                pattern["human_overrides"].append(feedback_record["humanOverride"])

    def _load_patterns(self, tenant_id: str) -> dict[str, Any]:
        """
        Load patterns from persisted feedback.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary of patterns
        """
        # Return in-memory patterns if available
        if tenant_id in self._patterns:
            return self._patterns[tenant_id]
        
        # Otherwise, load from JSONL file
        feedback_file = self.storage_dir / f"{tenant_id}.jsonl"
        if not feedback_file.exists():
            return {}
        
        patterns: dict[str, Any] = {}
        
        try:
            with open(feedback_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    feedback_record = json.loads(line)
                    
                    exception_type = feedback_record.get("exceptionType")
                    if exception_type:
                        pattern_key = f"exception_type:{exception_type}"
                        if pattern_key not in patterns:
                            patterns[pattern_key] = {
                                "count": 0,
                                "outcomes": defaultdict(int),
                                "human_overrides": [],
                                "severities": defaultdict(int),
                            }
                        
                        pattern = patterns[pattern_key]
                        pattern["count"] += 1
                        pattern["outcomes"][feedback_record.get("outcome", "UNKNOWN")] += 1
                        
                        if feedback_record.get("severity"):
                            pattern["severities"][feedback_record["severity"]] += 1
                        
                        if feedback_record.get("humanOverride"):
                            pattern["human_overrides"].append(feedback_record["humanOverride"])
        except Exception as e:
            logger.warning(f"Failed to load patterns for tenant {tenant_id}: {e}")
        
        # Cache in memory
        self._patterns[tenant_id] = patterns
        
        return patterns

    def _detect_recurring_exceptions(
        self, patterns: dict[str, Any], min_confidence: float
    ) -> list[PolicySuggestion]:
        """
        Detect recurring exceptions and suggest policy updates.
        
        Args:
            patterns: Pattern data
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of policy suggestions
        """
        suggestions = []
        
        for pattern_key, pattern_data in patterns.items():
            count = pattern_data.get("count", 0)
            
            # If exception type appears frequently, suggest severity override or approval rule
            if count >= 5:  # Threshold for "recurring"
                exception_type = pattern_key.replace("exception_type:", "")
                
                # Check if severity is consistent
                severities = pattern_data.get("severities", {})
                if len(severities) == 1:
                    severity = list(severities.keys())[0]
                    confidence = min(0.9, 0.5 + (count / 20))  # Higher confidence with more occurrences
                    
                    if confidence >= min_confidence:
                        suggestions.append(
                            PolicySuggestion(
                                suggestion_type="severity_override",
                                description=f"Exception type '{exception_type}' appears {count} times with consistent severity '{severity}'",
                                rationale=f"Consider adding severity override for '{exception_type}' to '{severity}'",
                                confidence=confidence,
                                suggested_change={
                                    "exceptionType": exception_type,
                                    "severity": severity,
                                },
                            )
                        )
        
        return suggestions

    def _detect_success_failure_patterns(
        self, patterns: dict[str, Any], min_confidence: float
    ) -> list[PolicySuggestion]:
        """
        Detect success/failure patterns and suggest policy updates.
        
        Args:
            patterns: Pattern data
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of policy suggestions
        """
        suggestions = []
        
        for pattern_key, pattern_data in patterns.items():
            outcomes = pattern_data.get("outcomes", {})
            total = sum(outcomes.values())
            
            if total < 3:  # Need at least 3 occurrences
                continue
            
            exception_type = pattern_key.replace("exception_type:", "")
            
            # Check failure rate
            failures = outcomes.get("FAILED", 0) + outcomes.get("ESCALATED", 0)
            failure_rate = failures / total if total > 0 else 0
            
            # If high failure rate, suggest approval rule
            if failure_rate > 0.5:  # More than 50% failure
                confidence = min(0.9, 0.6 + (failure_rate - 0.5) * 0.6)
                
                if confidence >= min_confidence:
                    suggestions.append(
                        PolicySuggestion(
                            suggestion_type="approval_rule",
                            description=f"Exception type '{exception_type}' has high failure rate ({failure_rate:.1%})",
                            rationale=f"Consider requiring human approval for '{exception_type}' due to high failure rate",
                            confidence=confidence,
                            suggested_change={
                                "exceptionType": exception_type,
                                "requireApproval": True,
                            },
                        )
                    )
            
            # Check success rate
            successes = outcomes.get("SUCCESS", 0) + outcomes.get("RESOLVED", 0)
            success_rate = successes / total if total > 0 else 0
            
            # If high success rate, suggest auto-approval
            if success_rate > 0.8 and total >= 5:  # More than 80% success with at least 5 occurrences
                confidence = min(0.9, 0.7 + (success_rate - 0.8) * 1.0)
                
                if confidence >= min_confidence:
                    suggestions.append(
                        PolicySuggestion(
                            suggestion_type="auto_approval",
                            description=f"Exception type '{exception_type}' has high success rate ({success_rate:.1%})",
                            rationale=f"Consider auto-approving '{exception_type}' due to high success rate",
                            confidence=confidence,
                            suggested_change={
                                "exceptionType": exception_type,
                                "autoApprove": True,
                            },
                        )
                    )
        
        return suggestions

    def _detect_human_override_patterns(
        self, patterns: dict[str, Any], min_confidence: float
    ) -> list[PolicySuggestion]:
        """
        Detect human override patterns and suggest policy updates.
        
        Args:
            patterns: Pattern data
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of policy suggestions
        """
        suggestions = []
        
        for pattern_key, pattern_data in patterns.items():
            human_overrides = pattern_data.get("human_overrides", [])
            total = pattern_data.get("count", 0)
            
            if len(human_overrides) == 0 or total < 3:
                continue
            
            exception_type = pattern_key.replace("exception_type:", "")
            override_rate = len(human_overrides) / total if total > 0 else 0
            
            # If frequent human overrides, suggest policy update
            if override_rate > 0.3:  # More than 30% overrides
                confidence = min(0.9, 0.7 + (override_rate - 0.3) * 0.67)
                
                if confidence >= min_confidence:
                    # Analyze override patterns
                    override_types = defaultdict(int)
                    for override in human_overrides:
                        override_type = override.get("type", "unknown")
                        override_types[override_type] += 1
                    
                    most_common_override = max(override_types.items(), key=lambda x: x[1])[0] if override_types else "unknown"
                    
                    suggestions.append(
                        PolicySuggestion(
                            suggestion_type="policy_update",
                            description=f"Exception type '{exception_type}' has frequent human overrides ({override_rate:.1%})",
                            rationale=f"Consider updating policy for '{exception_type}' based on override pattern: {most_common_override}",
                            confidence=confidence,
                            suggested_change={
                                "exceptionType": exception_type,
                                "overridePattern": most_common_override,
                                "overrideRate": override_rate,
                            },
                        )
                    )
        
        return suggestions

