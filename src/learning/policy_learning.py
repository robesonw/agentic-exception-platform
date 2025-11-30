"""
Policy Learning and Improvement for Phase 2 and Phase 3.

Phase 2:
- ingest_feedback(exceptionId, outcome, human_override)
- Pattern detection for recurring exceptions
- Success/failure pattern detection
- Policy suggestion generation (not auto-applied)

Phase 3:
- Per-policy-rule outcome tracking (success_count, failure_count, MTTR, false_positives, false_negatives)
- Enhanced policy improvement suggestions with impact estimates
- Outcome analysis and suggestions persistence

Safety:
- Suggestions only, never auto-edit tenant policies

Matches specification from:
- phase2-mvp-issues.md Issue 35
- phase3-mvp-issues.md P3-7
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import severity recommender for integration
try:
    from src.learning.severity_recommender import SeverityRecommender
except ImportError:
    SeverityRecommender = None  # Type: ignore
    logger.debug("SeverityRecommender not available")


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


class PolicyRuleOutcome(BaseModel):
    """
    Outcome tracking for a specific policy rule.
    
    Phase 3: Tracks per-rule metrics for analysis.
    """

    rule_id: str = Field(..., description="Identifier for the policy rule")
    success_count: int = Field(default=0, ge=0, description="Number of successful outcomes")
    failure_count: int = Field(default=0, ge=0, description="Number of failed outcomes")
    false_positive_count: int = Field(default=0, ge=0, description="Number of false positives (blocked when should allow)")
    false_negative_count: int = Field(default=0, ge=0, description="Number of false negatives (allowed when should block)")
    mttr_seconds: list[float] = Field(default_factory=list, description="List of MTTR values in seconds")
    total_count: int = Field(default=0, ge=0, description="Total number of times rule was evaluated")


class Suggestion(BaseModel):
    """
    Policy improvement suggestion with detailed analysis.
    
    Phase 3: Enhanced suggestion format with rule-level analysis.
    """

    rule_id: str = Field(..., description="Identifier for the policy rule being suggested for change")
    detected_issue: str = Field(..., description="Issue detected (e.g., 'too_strict', 'too_lenient', 'low_effectiveness')")
    proposed_change: str = Field(..., description="Description of proposed change (not applied, description only)")
    impact_estimate: str = Field(..., description="Estimated impact based on metrics (e.g., 'High: 80% false positive rate')")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in suggestion")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Supporting metrics for the suggestion")


class PolicyLearning:
    """
    Policy learning from human corrections and overrides.
    
    Responsibilities:
    - Ingest feedback from exception processing
    - Detect recurring exceptions and patterns
    - Generate policy suggestions (not auto-applied)
    - Store learning artifacts per tenant
    """

    def __init__(self, storage_dir: str = "./runtime/learning", severity_recommender: Optional[Any] = None):
        """
        Initialize PolicyLearning.
        
        Args:
            storage_dir: Directory for storing learning artifacts
            severity_recommender: Optional SeverityRecommender instance for Phase 3 integration
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory pattern tracking (per tenant)
        # Structure: {tenant_id: {pattern_key: pattern_data}}
        self._patterns: dict[str, dict[str, Any]] = defaultdict(dict)
        
        # Phase 3: Per-rule outcome tracking (per tenant)
        # Structure: {tenant_id: {rule_id: PolicyRuleOutcome}}
        self._rule_outcomes: dict[str, dict[str, PolicyRuleOutcome]] = defaultdict(dict)
        
        # Phase 3: Track exception processing times for MTTR calculation
        # Structure: {exception_id: (start_time, end_time)}
        self._processing_times: dict[str, tuple[datetime, Optional[datetime]]] = {}
        
        # Phase 3: Severity recommender integration
        self.severity_recommender = severity_recommender

    def ingest_feedback(
        self,
        tenant_id: str,
        exception_id: str,
        outcome: str,
        human_override: Optional[dict[str, Any]] = None,
        exception_type: Optional[str] = None,
        severity: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        resolution_successful: Optional[bool] = None,
        policy_rules_applied: Optional[list[str]] = None,
    ) -> None:
        """
        Ingest feedback for learning.
        
        Phase 3: Enhanced with per-rule outcome tracking and resolution success tracking.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            outcome: Outcome string (e.g., "SUCCESS", "FAILED", "ESCALATED")
            human_override: Optional human override information
            exception_type: Optional exception type
            severity: Optional severity level
            context: Optional context from processing
            resolution_successful: Optional boolean indicating if resolution was successful (Phase 3)
            policy_rules_applied: Optional list of policy rule IDs that were applied (Phase 3)
            
        Raises:
            PolicyLearningError: If ingestion fails
        """
        try:
            # Phase 3: Calculate MTTR if we have processing times
            mttr_seconds: Optional[float] = None
            if exception_id in self._processing_times:
                start_time, end_time = self._processing_times[exception_id]
                if end_time:
                    mttr_seconds = (end_time - start_time).total_seconds()
                # Clean up after use
                del self._processing_times[exception_id]
            elif mttr_seconds is None:
                # If mttr_seconds not provided and no processing times, try to get from context
                if context and "mttrSeconds" in context:
                    mttr_seconds = context.get("mttrSeconds")
            
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
                "resolutionSuccessful": resolution_successful,
                "policyRulesApplied": policy_rules_applied or [],
                "mttrSeconds": mttr_seconds,
            }
            
            # Persist to tenant-specific JSONL file
            self._persist_feedback(tenant_id, feedback_record)
            
            # Update pattern tracking
            self._update_patterns(tenant_id, feedback_record)
            
            # Phase 3: Update per-rule outcome tracking
            if policy_rules_applied:
                self._update_rule_outcomes(
                    tenant_id, policy_rules_applied, outcome, resolution_successful, human_override, mttr_seconds
                )
            
            logger.debug(
                f"Ingested feedback for exception {exception_id} "
                f"(tenant: {tenant_id}, outcome: {outcome}, rules: {len(policy_rules_applied or [])})"
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

    def _update_rule_outcomes(
        self,
        tenant_id: str,
        rule_ids: list[str],
        outcome: str,
        resolution_successful: Optional[bool],
        human_override: Optional[dict[str, Any]],
        mttr_seconds: Optional[float],
    ) -> None:
        """
        Update per-rule outcome tracking.
        
        Phase 3: Tracks success/failure counts, MTTR, and false positives/negatives.
        
        Args:
            tenant_id: Tenant identifier
            rule_ids: List of policy rule IDs that were applied
            outcome: Outcome string
            resolution_successful: Whether resolution was successful
            human_override: Human override information (if any)
            mttr_seconds: MTTR in seconds (if available)
        """
        if tenant_id not in self._rule_outcomes:
            self._rule_outcomes[tenant_id] = {}
        
        for rule_id in rule_ids:
            if rule_id not in self._rule_outcomes[tenant_id]:
                self._rule_outcomes[tenant_id][rule_id] = PolicyRuleOutcome(rule_id=rule_id)
            
            rule_outcome = self._rule_outcomes[tenant_id][rule_id]
            rule_outcome.total_count += 1
            
            # Track success/failure
            if resolution_successful is True:
                rule_outcome.success_count += 1
            elif resolution_successful is False:
                rule_outcome.failure_count += 1
            elif outcome in ("SUCCESS", "RESOLVED"):
                rule_outcome.success_count += 1
            elif outcome in ("FAILED", "ESCALATED"):
                rule_outcome.failure_count += 1
            
            # Track MTTR
            if mttr_seconds is not None:
                rule_outcome.mttr_seconds.append(mttr_seconds)
                # Keep only last 100 MTTR values to avoid unbounded growth
                if len(rule_outcome.mttr_seconds) > 100:
                    rule_outcome.mttr_seconds = rule_outcome.mttr_seconds[-100:]
            
            # Track false positives/negatives based on human overrides
            if human_override:
                override_type = human_override.get("type", "")
                override_reason = str(human_override.get("reason", "")).lower()
                
                # False negative: rule allowed when human overrode to block (check this first as it's more specific)
                if ("should have blocked" in override_reason or "should block" in override_reason) or ("too lenient" in override_reason and ("should" in override_reason or "block" in override_reason)):
                    rule_outcome.false_negative_count += 1
                # False positive: rule blocked when human overrode to allow
                elif ("blocked" in override_reason and "should have allowed" in override_reason) or ("too strict" in override_reason):
                    rule_outcome.false_positive_count += 1

    def suggest_policy_improvements(self, tenant_id: str) -> list[Suggestion]:
        """
        Suggest policy improvements based on per-rule outcome analysis.
        
        Phase 3: Analyzes per-rule metrics to detect issues and suggest improvements.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of policy improvement suggestions (not auto-applied)
        """
        suggestions = []
        
        # Load rule outcomes for tenant
        if tenant_id not in self._rule_outcomes:
            logger.debug(f"No rule outcomes found for tenant {tenant_id}")
            return suggestions
        
        rule_outcomes = self._rule_outcomes[tenant_id]
        
        for rule_id, outcome in rule_outcomes.items():
            if outcome.total_count < 3:  # Need at least 3 evaluations
                continue
            
            # Calculate metrics
            total = outcome.total_count
            success_rate = outcome.success_count / total if total > 0 else 0
            failure_rate = outcome.failure_count / total if total > 0 else 0
            false_positive_rate = outcome.false_positive_count / total if total > 0 else 0
            false_negative_rate = outcome.false_negative_count / total if total > 0 else 0
            
            # Calculate average MTTR
            avg_mttr = sum(outcome.mttr_seconds) / len(outcome.mttr_seconds) if outcome.mttr_seconds else None
            
            # Detect issues and generate suggestions
            
            # Issue 1: Too strict (high false positive rate)
            if false_positive_rate > 0.2:  # More than 20% false positives
                detected_issue = "too_strict"
                proposed_change = f"Consider relaxing rule '{rule_id}' - {false_positive_rate:.1%} false positive rate"
                impact_estimate = f"High: {false_positive_rate:.1%} false positive rate ({outcome.false_positive_count}/{total})"
                confidence = min(0.9, 0.6 + (false_positive_rate - 0.2) * 0.75)
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics={
                            "false_positive_rate": false_positive_rate,
                            "false_positive_count": outcome.false_positive_count,
                            "total_count": total,
                        },
                    )
                )
            
            # Issue 2: Too lenient (high false negative rate)
            if false_negative_rate > 0.2:  # More than 20% false negatives
                detected_issue = "too_lenient"
                proposed_change = f"Consider tightening rule '{rule_id}' - {false_negative_rate:.1%} false negative rate"
                impact_estimate = f"High: {false_negative_rate:.1%} false negative rate ({outcome.false_negative_count}/{total})"
                confidence = min(0.9, 0.6 + (false_negative_rate - 0.2) * 0.75)
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics={
                            "false_negative_rate": false_negative_rate,
                            "false_negative_count": outcome.false_negative_count,
                            "total_count": total,
                        },
                    )
                )
            
            # Issue 3: Low effectiveness (high failure rate)
            if failure_rate > 0.5 and total >= 5:  # More than 50% failure with at least 5 evaluations
                detected_issue = "low_effectiveness"
                proposed_change = f"Rule '{rule_id}' has low effectiveness - {failure_rate:.1%} failure rate"
                impact_estimate = f"Medium: {failure_rate:.1%} failure rate ({outcome.failure_count}/{total})"
                confidence = min(0.9, 0.5 + (failure_rate - 0.5) * 0.8)
                
                metrics = {
                    "failure_rate": failure_rate,
                    "failure_count": outcome.failure_count,
                    "success_count": outcome.success_count,
                    "total_count": total,
                }
                
                if avg_mttr:
                    metrics["avg_mttr_seconds"] = avg_mttr
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics=metrics,
                    )
                )
            
            # Issue 4: High MTTR (if available)
            if avg_mttr and avg_mttr > 3600:  # More than 1 hour average MTTR
                detected_issue = "high_mttr"
                proposed_change = f"Rule '{rule_id}' associated with high MTTR - {avg_mttr/60:.1f} minutes average"
                impact_estimate = f"Medium: Average MTTR {avg_mttr/60:.1f} minutes"
                confidence = min(0.85, 0.5 + (avg_mttr - 3600) / 3600 * 0.35)
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics={
                            "avg_mttr_seconds": avg_mttr,
                            "mttr_count": len(outcome.mttr_seconds),
                        },
                    )
                )
        
        # Sort by confidence (highest first)
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        # Persist suggestions
        self._persist_suggestions(tenant_id, suggestions)
        
        logger.info(
            f"Generated {len(suggestions)} policy improvement suggestions for tenant {tenant_id}"
        )
        
        return suggestions

    def _persist_suggestions(self, tenant_id: str, suggestions: list[Suggestion]) -> None:
        """
        Persist policy suggestions to tenant-specific JSONL file.
        
        Phase 3: Stores suggestions for later review.
        
        Args:
            tenant_id: Tenant identifier
            suggestions: List of suggestions to persist
        """
        suggestions_file = self.storage_dir / f"{tenant_id}_policy_suggestions.jsonl"
        
        # Append each suggestion as a JSONL line
        with open(suggestions_file, "a", encoding="utf-8") as f:
            for suggestion in suggestions:
                suggestion_dict = suggestion.model_dump()
                suggestion_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(suggestion_dict, default=str) + "\n")
        
        logger.debug(f"Persisted {len(suggestions)} suggestions to {suggestions_file}")

    def get_combined_suggestions(
        self,
        tenant_id: str,
        domain_name: Optional[str] = None,
        include_severity_rules: bool = True,
    ) -> dict[str, Any]:
        """
        Get combined suggestions from policy learning and severity recommender.
        
        Phase 3: Aggregates policy improvement suggestions and severity rule suggestions
        into a combined report.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Optional domain name identifier (required for severity rules)
            include_severity_rules: Whether to include severity rule suggestions
            
        Returns:
            Dictionary with combined suggestions
        """
        combined = {
            "tenant_id": tenant_id,
            "domain_name": domain_name,
            "policy_suggestions": [],
            "severity_rule_suggestions": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Get policy improvement suggestions
        policy_suggestions = self.suggest_policy_improvements(tenant_id)
        combined["policy_suggestions"] = [s.model_dump() for s in policy_suggestions]
        
        # Get severity rule suggestions if requested and recommender is available
        if include_severity_rules and self.severity_recommender and domain_name:
            try:
                severity_suggestions = self.severity_recommender.analyze_severity_patterns(
                    tenant_id, domain_name
                )
                combined["severity_rule_suggestions"] = [s.model_dump() for s in severity_suggestions]
            except Exception as e:
                logger.warning(f"Failed to get severity rule suggestions: {e}")
                combined["severity_rule_suggestions"] = []
        
        logger.info(
            f"Generated combined suggestions for tenant {tenant_id}: "
            f"{len(combined['policy_suggestions'])} policy, "
            f"{len(combined['severity_rule_suggestions'])} severity rules"
        )
        
        return combined

    def record_processing_start(self, exception_id: str) -> None:
        """
        Record the start of exception processing for MTTR calculation.
        
        Phase 3: Tracks processing start time.
        
        Args:
            exception_id: Exception identifier
        """
        self._processing_times[exception_id] = (datetime.now(timezone.utc), None)

    def record_processing_end(self, exception_id: str) -> None:
        """
        Record the end of exception processing for MTTR calculation.
        
        Phase 3: Tracks processing end time.
        
        Args:
            exception_id: Exception identifier
        """
        if exception_id in self._processing_times:
            start_time, _ = self._processing_times[exception_id]
            self._processing_times[exception_id] = (start_time, datetime.now(timezone.utc))

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

    def _update_rule_outcomes(
        self,
        tenant_id: str,
        rule_ids: list[str],
        outcome: str,
        resolution_successful: Optional[bool],
        human_override: Optional[dict[str, Any]],
        mttr_seconds: Optional[float],
    ) -> None:
        """
        Update per-rule outcome tracking.
        
        Phase 3: Tracks success/failure counts, MTTR, and false positives/negatives.
        
        Args:
            tenant_id: Tenant identifier
            rule_ids: List of policy rule IDs that were applied
            outcome: Outcome string
            resolution_successful: Whether resolution was successful
            human_override: Human override information (if any)
            mttr_seconds: MTTR in seconds (if available)
        """
        if tenant_id not in self._rule_outcomes:
            self._rule_outcomes[tenant_id] = {}
        
        for rule_id in rule_ids:
            if rule_id not in self._rule_outcomes[tenant_id]:
                self._rule_outcomes[tenant_id][rule_id] = PolicyRuleOutcome(rule_id=rule_id)
            
            rule_outcome = self._rule_outcomes[tenant_id][rule_id]
            rule_outcome.total_count += 1
            
            # Track success/failure
            if resolution_successful is True:
                rule_outcome.success_count += 1
            elif resolution_successful is False:
                rule_outcome.failure_count += 1
            elif outcome in ("SUCCESS", "RESOLVED"):
                rule_outcome.success_count += 1
            elif outcome in ("FAILED", "ESCALATED"):
                rule_outcome.failure_count += 1
            
            # Track MTTR
            if mttr_seconds is not None:
                rule_outcome.mttr_seconds.append(mttr_seconds)
                # Keep only last 100 MTTR values to avoid unbounded growth
                if len(rule_outcome.mttr_seconds) > 100:
                    rule_outcome.mttr_seconds = rule_outcome.mttr_seconds[-100:]
            
            # Track false positives/negatives based on human overrides
            if human_override:
                override_type = human_override.get("type", "")
                override_reason = str(human_override.get("reason", "")).lower()
                
                # False negative: rule allowed when human overrode to block (check this first as it's more specific)
                if ("should have blocked" in override_reason or "should block" in override_reason) or ("too lenient" in override_reason and ("should" in override_reason or "block" in override_reason)):
                    rule_outcome.false_negative_count += 1
                # False positive: rule blocked when human overrode to allow
                elif ("blocked" in override_reason and "should have allowed" in override_reason) or ("too strict" in override_reason):
                    rule_outcome.false_positive_count += 1

    def suggest_policy_improvements(self, tenant_id: str) -> list[Suggestion]:
        """
        Suggest policy improvements based on per-rule outcome analysis.
        
        Phase 3: Analyzes per-rule metrics to detect issues and suggest improvements.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of policy improvement suggestions (not auto-applied)
        """
        suggestions = []
        
        # Load rule outcomes for tenant
        if tenant_id not in self._rule_outcomes:
            logger.debug(f"No rule outcomes found for tenant {tenant_id}")
            return suggestions
        
        rule_outcomes = self._rule_outcomes[tenant_id]
        
        for rule_id, outcome in rule_outcomes.items():
            if outcome.total_count < 3:  # Need at least 3 evaluations
                continue
            
            # Calculate metrics
            total = outcome.total_count
            success_rate = outcome.success_count / total if total > 0 else 0
            failure_rate = outcome.failure_count / total if total > 0 else 0
            false_positive_rate = outcome.false_positive_count / total if total > 0 else 0
            false_negative_rate = outcome.false_negative_count / total if total > 0 else 0
            
            # Calculate average MTTR
            avg_mttr = sum(outcome.mttr_seconds) / len(outcome.mttr_seconds) if outcome.mttr_seconds else None
            
            # Detect issues and generate suggestions
            
            # Issue 1: Too strict (high false positive rate)
            if false_positive_rate > 0.2:  # More than 20% false positives
                detected_issue = "too_strict"
                proposed_change = f"Consider relaxing rule '{rule_id}' - {false_positive_rate:.1%} false positive rate"
                impact_estimate = f"High: {false_positive_rate:.1%} false positive rate ({outcome.false_positive_count}/{total})"
                confidence = min(0.9, 0.6 + (false_positive_rate - 0.2) * 0.75)
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics={
                            "false_positive_rate": false_positive_rate,
                            "false_positive_count": outcome.false_positive_count,
                            "total_count": total,
                        },
                    )
                )
            
            # Issue 2: Too lenient (high false negative rate)
            if false_negative_rate > 0.2:  # More than 20% false negatives
                detected_issue = "too_lenient"
                proposed_change = f"Consider tightening rule '{rule_id}' - {false_negative_rate:.1%} false negative rate"
                impact_estimate = f"High: {false_negative_rate:.1%} false negative rate ({outcome.false_negative_count}/{total})"
                confidence = min(0.9, 0.6 + (false_negative_rate - 0.2) * 0.75)
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics={
                            "false_negative_rate": false_negative_rate,
                            "false_negative_count": outcome.false_negative_count,
                            "total_count": total,
                        },
                    )
                )
            
            # Issue 3: Low effectiveness (high failure rate)
            if failure_rate > 0.5 and total >= 5:  # More than 50% failure with at least 5 evaluations
                detected_issue = "low_effectiveness"
                proposed_change = f"Rule '{rule_id}' has low effectiveness - {failure_rate:.1%} failure rate"
                impact_estimate = f"Medium: {failure_rate:.1%} failure rate ({outcome.failure_count}/{total})"
                confidence = min(0.9, 0.5 + (failure_rate - 0.5) * 0.8)
                
                metrics = {
                    "failure_rate": failure_rate,
                    "failure_count": outcome.failure_count,
                    "success_count": outcome.success_count,
                    "total_count": total,
                }
                
                if avg_mttr:
                    metrics["avg_mttr_seconds"] = avg_mttr
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics=metrics,
                    )
                )
            
            # Issue 4: High MTTR (if available)
            if avg_mttr and avg_mttr > 3600:  # More than 1 hour average MTTR
                detected_issue = "high_mttr"
                proposed_change = f"Rule '{rule_id}' associated with high MTTR - {avg_mttr/60:.1f} minutes average"
                impact_estimate = f"Medium: Average MTTR {avg_mttr/60:.1f} minutes"
                confidence = min(0.85, 0.5 + (avg_mttr - 3600) / 3600 * 0.35)
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics={
                            "avg_mttr_seconds": avg_mttr,
                            "mttr_count": len(outcome.mttr_seconds),
                        },
                    )
                )
        
        # Sort by confidence (highest first)
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        # Persist suggestions
        self._persist_suggestions(tenant_id, suggestions)
        
        logger.info(
            f"Generated {len(suggestions)} policy improvement suggestions for tenant {tenant_id}"
        )
        
        return suggestions

    def _persist_suggestions(self, tenant_id: str, suggestions: list[Suggestion]) -> None:
        """
        Persist policy suggestions to tenant-specific JSONL file.
        
        Phase 3: Stores suggestions for later review.
        
        Args:
            tenant_id: Tenant identifier
            suggestions: List of suggestions to persist
        """
        suggestions_file = self.storage_dir / f"{tenant_id}_policy_suggestions.jsonl"
        
        # Append each suggestion as a JSONL line
        with open(suggestions_file, "a", encoding="utf-8") as f:
            for suggestion in suggestions:
                suggestion_dict = suggestion.model_dump()
                suggestion_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(suggestion_dict, default=str) + "\n")
        
        logger.debug(f"Persisted {len(suggestions)} suggestions to {suggestions_file}")

    def get_combined_suggestions(
        self,
        tenant_id: str,
        domain_name: Optional[str] = None,
        include_severity_rules: bool = True,
    ) -> dict[str, Any]:
        """
        Get combined suggestions from policy learning and severity recommender.
        
        Phase 3: Aggregates policy improvement suggestions and severity rule suggestions
        into a combined report.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Optional domain name identifier (required for severity rules)
            include_severity_rules: Whether to include severity rule suggestions
            
        Returns:
            Dictionary with combined suggestions
        """
        combined = {
            "tenant_id": tenant_id,
            "domain_name": domain_name,
            "policy_suggestions": [],
            "severity_rule_suggestions": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Get policy improvement suggestions
        policy_suggestions = self.suggest_policy_improvements(tenant_id)
        combined["policy_suggestions"] = [s.model_dump() for s in policy_suggestions]
        
        # Get severity rule suggestions if requested and recommender is available
        if include_severity_rules and self.severity_recommender and domain_name:
            try:
                severity_suggestions = self.severity_recommender.analyze_severity_patterns(
                    tenant_id, domain_name
                )
                combined["severity_rule_suggestions"] = [s.model_dump() for s in severity_suggestions]
            except Exception as e:
                logger.warning(f"Failed to get severity rule suggestions: {e}")
                combined["severity_rule_suggestions"] = []
        
        logger.info(
            f"Generated combined suggestions for tenant {tenant_id}: "
            f"{len(combined['policy_suggestions'])} policy, "
            f"{len(combined['severity_rule_suggestions'])} severity rules"
        )
        
        return combined

    def record_processing_start(self, exception_id: str) -> None:
        """
        Record the start of exception processing for MTTR calculation.
        
        Phase 3: Tracks processing start time.
        
        Args:
            exception_id: Exception identifier
        """
        self._processing_times[exception_id] = (datetime.now(timezone.utc), None)

    def record_processing_end(self, exception_id: str) -> None:
        """
        Record the end of exception processing for MTTR calculation.
        
        Phase 3: Tracks processing end time.
        
        Args:
            exception_id: Exception identifier
        """
        if exception_id in self._processing_times:
            start_time, _ = self._processing_times[exception_id]
            self._processing_times[exception_id] = (start_time, datetime.now(timezone.utc))

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

    def _update_rule_outcomes(
        self,
        tenant_id: str,
        rule_ids: list[str],
        outcome: str,
        resolution_successful: Optional[bool],
        human_override: Optional[dict[str, Any]],
        mttr_seconds: Optional[float],
    ) -> None:
        """
        Update per-rule outcome tracking.
        
        Phase 3: Tracks success/failure counts, MTTR, and false positives/negatives.
        
        Args:
            tenant_id: Tenant identifier
            rule_ids: List of policy rule IDs that were applied
            outcome: Outcome string
            resolution_successful: Whether resolution was successful
            human_override: Human override information (if any)
            mttr_seconds: MTTR in seconds (if available)
        """
        if tenant_id not in self._rule_outcomes:
            self._rule_outcomes[tenant_id] = {}
        
        for rule_id in rule_ids:
            if rule_id not in self._rule_outcomes[tenant_id]:
                self._rule_outcomes[tenant_id][rule_id] = PolicyRuleOutcome(rule_id=rule_id)
            
            rule_outcome = self._rule_outcomes[tenant_id][rule_id]
            rule_outcome.total_count += 1
            
            # Track success/failure
            if resolution_successful is True:
                rule_outcome.success_count += 1
            elif resolution_successful is False:
                rule_outcome.failure_count += 1
            elif outcome in ("SUCCESS", "RESOLVED"):
                rule_outcome.success_count += 1
            elif outcome in ("FAILED", "ESCALATED"):
                rule_outcome.failure_count += 1
            
            # Track MTTR
            if mttr_seconds is not None:
                rule_outcome.mttr_seconds.append(mttr_seconds)
                # Keep only last 100 MTTR values to avoid unbounded growth
                if len(rule_outcome.mttr_seconds) > 100:
                    rule_outcome.mttr_seconds = rule_outcome.mttr_seconds[-100:]
            
            # Track false positives/negatives based on human overrides
            if human_override:
                override_type = human_override.get("type", "")
                override_reason = str(human_override.get("reason", "")).lower()
                
                # False negative: rule allowed when human overrode to block (check this first as it's more specific)
                if ("should have blocked" in override_reason or "should block" in override_reason) or ("too lenient" in override_reason and ("should" in override_reason or "block" in override_reason)):
                    rule_outcome.false_negative_count += 1
                # False positive: rule blocked when human overrode to allow
                elif ("blocked" in override_reason and "should have allowed" in override_reason) or ("too strict" in override_reason):
                    rule_outcome.false_positive_count += 1

    def suggest_policy_improvements(self, tenant_id: str) -> list[Suggestion]:
        """
        Suggest policy improvements based on per-rule outcome analysis.
        
        Phase 3: Analyzes per-rule metrics to detect issues and suggest improvements.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of policy improvement suggestions (not auto-applied)
        """
        suggestions = []
        
        # Load rule outcomes for tenant
        if tenant_id not in self._rule_outcomes:
            logger.debug(f"No rule outcomes found for tenant {tenant_id}")
            return suggestions
        
        rule_outcomes = self._rule_outcomes[tenant_id]
        
        for rule_id, outcome in rule_outcomes.items():
            if outcome.total_count < 3:  # Need at least 3 evaluations
                continue
            
            # Calculate metrics
            total = outcome.total_count
            success_rate = outcome.success_count / total if total > 0 else 0
            failure_rate = outcome.failure_count / total if total > 0 else 0
            false_positive_rate = outcome.false_positive_count / total if total > 0 else 0
            false_negative_rate = outcome.false_negative_count / total if total > 0 else 0
            
            # Calculate average MTTR
            avg_mttr = sum(outcome.mttr_seconds) / len(outcome.mttr_seconds) if outcome.mttr_seconds else None
            
            # Detect issues and generate suggestions
            
            # Issue 1: Too strict (high false positive rate)
            if false_positive_rate > 0.2:  # More than 20% false positives
                detected_issue = "too_strict"
                proposed_change = f"Consider relaxing rule '{rule_id}' - {false_positive_rate:.1%} false positive rate"
                impact_estimate = f"High: {false_positive_rate:.1%} false positive rate ({outcome.false_positive_count}/{total})"
                confidence = min(0.9, 0.6 + (false_positive_rate - 0.2) * 0.75)
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics={
                            "false_positive_rate": false_positive_rate,
                            "false_positive_count": outcome.false_positive_count,
                            "total_count": total,
                        },
                    )
                )
            
            # Issue 2: Too lenient (high false negative rate)
            if false_negative_rate > 0.2:  # More than 20% false negatives
                detected_issue = "too_lenient"
                proposed_change = f"Consider tightening rule '{rule_id}' - {false_negative_rate:.1%} false negative rate"
                impact_estimate = f"High: {false_negative_rate:.1%} false negative rate ({outcome.false_negative_count}/{total})"
                confidence = min(0.9, 0.6 + (false_negative_rate - 0.2) * 0.75)
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics={
                            "false_negative_rate": false_negative_rate,
                            "false_negative_count": outcome.false_negative_count,
                            "total_count": total,
                        },
                    )
                )
            
            # Issue 3: Low effectiveness (high failure rate)
            if failure_rate > 0.5 and total >= 5:  # More than 50% failure with at least 5 evaluations
                detected_issue = "low_effectiveness"
                proposed_change = f"Rule '{rule_id}' has low effectiveness - {failure_rate:.1%} failure rate"
                impact_estimate = f"Medium: {failure_rate:.1%} failure rate ({outcome.failure_count}/{total})"
                confidence = min(0.9, 0.5 + (failure_rate - 0.5) * 0.8)
                
                metrics = {
                    "failure_rate": failure_rate,
                    "failure_count": outcome.failure_count,
                    "success_count": outcome.success_count,
                    "total_count": total,
                }
                
                if avg_mttr:
                    metrics["avg_mttr_seconds"] = avg_mttr
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics=metrics,
                    )
                )
            
            # Issue 4: High MTTR (if available)
            if avg_mttr and avg_mttr > 3600:  # More than 1 hour average MTTR
                detected_issue = "high_mttr"
                proposed_change = f"Rule '{rule_id}' associated with high MTTR - {avg_mttr/60:.1f} minutes average"
                impact_estimate = f"Medium: Average MTTR {avg_mttr/60:.1f} minutes"
                confidence = min(0.85, 0.5 + (avg_mttr - 3600) / 3600 * 0.35)
                
                suggestions.append(
                    Suggestion(
                        rule_id=rule_id,
                        detected_issue=detected_issue,
                        proposed_change=proposed_change,
                        impact_estimate=impact_estimate,
                        confidence=confidence,
                        metrics={
                            "avg_mttr_seconds": avg_mttr,
                            "mttr_count": len(outcome.mttr_seconds),
                        },
                    )
                )
        
        # Sort by confidence (highest first)
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        # Persist suggestions
        self._persist_suggestions(tenant_id, suggestions)
        
        logger.info(
            f"Generated {len(suggestions)} policy improvement suggestions for tenant {tenant_id}"
        )
        
        return suggestions

    def _persist_suggestions(self, tenant_id: str, suggestions: list[Suggestion]) -> None:
        """
        Persist policy suggestions to tenant-specific JSONL file.
        
        Phase 3: Stores suggestions for later review.
        
        Args:
            tenant_id: Tenant identifier
            suggestions: List of suggestions to persist
        """
        suggestions_file = self.storage_dir / f"{tenant_id}_policy_suggestions.jsonl"
        
        # Append each suggestion as a JSONL line
        with open(suggestions_file, "a", encoding="utf-8") as f:
            for suggestion in suggestions:
                suggestion_dict = suggestion.model_dump()
                suggestion_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(suggestion_dict, default=str) + "\n")
        
        logger.debug(f"Persisted {len(suggestions)} suggestions to {suggestions_file}")

    def get_combined_suggestions(
        self,
        tenant_id: str,
        domain_name: Optional[str] = None,
        include_severity_rules: bool = True,
    ) -> dict[str, Any]:
        """
        Get combined suggestions from policy learning and severity recommender.
        
        Phase 3: Aggregates policy improvement suggestions and severity rule suggestions
        into a combined report.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Optional domain name identifier (required for severity rules)
            include_severity_rules: Whether to include severity rule suggestions
            
        Returns:
            Dictionary with combined suggestions
        """
        combined = {
            "tenant_id": tenant_id,
            "domain_name": domain_name,
            "policy_suggestions": [],
            "severity_rule_suggestions": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Get policy improvement suggestions
        policy_suggestions = self.suggest_policy_improvements(tenant_id)
        combined["policy_suggestions"] = [s.model_dump() for s in policy_suggestions]
        
        # Get severity rule suggestions if requested and recommender is available
        if include_severity_rules and self.severity_recommender and domain_name:
            try:
                severity_suggestions = self.severity_recommender.analyze_severity_patterns(
                    tenant_id, domain_name
                )
                combined["severity_rule_suggestions"] = [s.model_dump() for s in severity_suggestions]
            except Exception as e:
                logger.warning(f"Failed to get severity rule suggestions: {e}")
                combined["severity_rule_suggestions"] = []
        
        logger.info(
            f"Generated combined suggestions for tenant {tenant_id}: "
            f"{len(combined['policy_suggestions'])} policy, "
            f"{len(combined['severity_rule_suggestions'])} severity rules"
        )
        
        return combined

    def record_processing_start(self, exception_id: str) -> None:
        """
        Record the start of exception processing for MTTR calculation.
        
        Phase 3: Tracks processing start time.
        
        Args:
            exception_id: Exception identifier
        """
        self._processing_times[exception_id] = (datetime.now(timezone.utc), None)

    def record_processing_end(self, exception_id: str) -> None:
        """
        Record the end of exception processing for MTTR calculation.
        
        Phase 3: Tracks processing end time.
        
        Args:
            exception_id: Exception identifier
        """
        if exception_id in self._processing_times:
            start_time, _ = self._processing_times[exception_id]
            self._processing_times[exception_id] = (start_time, datetime.now(timezone.utc))

