"""
Guardrail Adjustment Recommendation System for Phase 3.

Analyzes policy violations, false positives, and false negatives for guardrails
to suggest guardrail tuning and adjustments.

Safety:
- Suggestions only, never auto-edit guardrails
- All suggestions require human review and approval

Matches specification from phase3-mvp-issues.md P3-10.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict

from src.models.domain_pack import Guardrails
from src.models.tenant_policy import TenantPolicyPack

logger = logging.getLogger(__name__)


# Configurable thresholds for guardrail analysis
class GuardrailAnalysisConfig:
    """Configuration thresholds for guardrail analysis."""

    # High false positive ratio threshold (e.g., 0.7 = 70% false positives)
    HIGH_FALSE_POSITIVE_RATIO: float = 0.7

    # High false negative ratio threshold (e.g., 0.3 = 30% false negatives)
    HIGH_FALSE_NEGATIVE_RATIO: float = 0.3

    # Minimum sample size for reliable analysis
    MIN_SAMPLE_SIZE: int = 10

    # Confidence threshold for recommendations
    MIN_CONFIDENCE_THRESHOLD: float = 0.6


class GuardrailRecommendation(BaseModel):
    """
    Guardrail adjustment recommendation.
    
    Safety: These are suggestions only, never auto-applied.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    guardrail_id: str = Field(..., alias="guardrailId", description="Identifier for the guardrail")
    tenant_id: str = Field(..., alias="tenantId", description="Tenant identifier")
    current_config: dict[str, Any] = Field(..., alias="currentConfig", description="Current guardrail configuration")
    proposed_change: dict[str, Any] = Field(..., alias="proposedChange", description="Proposed guardrail change")
    reason: str = Field(..., description="Short natural language explanation")
    impact_analysis: dict[str, Any] = Field(..., alias="impactAnalysis", description="Impact analysis of the change")
    review_required: bool = Field(True, alias="reviewRequired", description="Whether human review is required")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="createdAt",
        description="Timestamp when recommendation was created",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the recommendation")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class GuardrailRecommenderError(Exception):
    """Raised when guardrail recommender operations fail."""

    pass


class GuardrailPerformanceMetrics:
    """Performance metrics for a guardrail."""

    def __init__(self, guardrail_id: str):
        """Initialize guardrail performance metrics."""
        self.guardrail_id = guardrail_id
        self.total_checks: int = 0
        self.blocked_count: int = 0
        self.allowed_count: int = 0
        self.false_positive_count: int = 0  # Blocked when should allow
        self.false_negative_count: int = 0  # Allowed when should block
        self.true_positive_count: int = 0  # Blocked when should block
        self.true_negative_count: int = 0  # Allowed when should allow
        self.violation_count: int = 0
        self.human_override_count: int = 0
        self.example_exceptions: list[str] = []

    def get_false_positive_ratio(self) -> float:
        """Calculate false positive ratio."""
        if self.total_checks == 0:
            return 0.0
        return self.false_positive_count / self.total_checks

    def get_false_negative_ratio(self) -> float:
        """Calculate false negative ratio."""
        if self.total_checks == 0:
            return 0.0
        return self.false_negative_count / self.total_checks

    def get_accuracy(self) -> float:
        """Calculate accuracy (true positives + true negatives / total)."""
        if self.total_checks == 0:
            return 0.0
        return (self.true_positive_count + self.true_negative_count) / self.total_checks


class GuardrailRecommender:
    """
    Guardrail adjustment recommendation engine.
    
    Analyzes policy violations, false positives, and false negatives for guardrails
    to suggest guardrail tuning and adjustments.
    
    Responsibilities:
    - Analyze guardrail performance metrics
    - Detect patterns of false positives/negatives
    - Generate guardrail adjustment suggestions
    - Provide impact analysis for recommendations
    - Store suggestions per tenant/domain
    """

    def __init__(self, storage_dir: str = "./runtime/learning"):
        """
        Initialize GuardrailRecommender.
        
        Args:
            storage_dir: Directory for storing learning artifacts
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.config = GuardrailAnalysisConfig()

    def analyze_guardrail_performance(
        self,
        tenant_id: str,
        domain_name: str,
        domain_pack: Any,
        tenant_policy: TenantPolicyPack,
        historical_decisions: Optional[list[dict[str, Any]]] = None,
        policy_violations: Optional[list[dict[str, Any]]] = None,
        metrics_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, GuardrailPerformanceMetrics]:
        """
        Analyze guardrail performance from historical data.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            domain_pack: DomainPack instance
            tenant_policy: TenantPolicyPack instance
            historical_decisions: Optional list of historical policy decisions
            policy_violations: Optional list of policy violation records
            metrics_data: Optional metrics data (false positives, false negatives, etc.)
            
        Returns:
            Dictionary mapping guardrail_id to GuardrailPerformanceMetrics
        """
        # Get guardrails (tenant policy overrides domain pack)
        guardrails = tenant_policy.custom_guardrails or domain_pack.guardrails
        
        # Initialize metrics for each guardrail aspect
        metrics: dict[str, GuardrailPerformanceMetrics] = {}
        
        # Track human_approval_threshold guardrail
        threshold_guardrail_id = "human_approval_threshold"
        metrics[threshold_guardrail_id] = GuardrailPerformanceMetrics(threshold_guardrail_id)
        
        # Track allow_lists guardrail
        allow_list_guardrail_id = "allow_lists"
        metrics[allow_list_guardrail_id] = GuardrailPerformanceMetrics(allow_list_guardrail_id)
        
        # Track block_lists guardrail
        block_list_guardrail_id = "block_lists"
        metrics[block_list_guardrail_id] = GuardrailPerformanceMetrics(block_list_guardrail_id)
        
        # Analyze historical decisions if provided
        if historical_decisions:
            for decision in historical_decisions:
                # Extract guardrail check results from decision
                evidence = decision.get("evidence", [])
                decision_result = decision.get("decision", "")
                
                # Check if guardrail blocked/allowed
                if "BLOCK" in decision_result.upper():
                    metrics[threshold_guardrail_id].blocked_count += 1
                    metrics[threshold_guardrail_id].total_checks += 1
                elif "ALLOW" in decision_result.upper():
                    metrics[threshold_guardrail_id].allowed_count += 1
                    metrics[threshold_guardrail_id].total_checks += 1
                
                # Check for human overrides (indicates false positive/negative)
                if "override" in str(evidence).lower() or "human" in str(evidence).lower():
                    if "BLOCK" in decision_result.upper():
                        metrics[threshold_guardrail_id].false_positive_count += 1
                    else:
                        metrics[threshold_guardrail_id].false_negative_count += 1
                    metrics[threshold_guardrail_id].human_override_count += 1
        
        # Analyze policy violations if provided
        if policy_violations:
            for violation in policy_violations:
                violation_type = violation.get("type", "")
                guardrail_id = violation.get("guardrail_id", threshold_guardrail_id)
                
                if guardrail_id not in metrics:
                    metrics[guardrail_id] = GuardrailPerformanceMetrics(guardrail_id)
                
                metrics[guardrail_id].violation_count += 1
                metrics[guardrail_id].total_checks += 1
                
                # Violations suggest false negatives (should have blocked)
                metrics[guardrail_id].false_negative_count += 1
        
        # Incorporate metrics data if provided
        if metrics_data:
            for guardrail_id, guardrail_metrics in metrics_data.items():
                if guardrail_id not in metrics:
                    metrics[guardrail_id] = GuardrailPerformanceMetrics(guardrail_id)
                
                perf_metrics = metrics[guardrail_id]
                perf_metrics.false_positive_count += guardrail_metrics.get("false_positive_count", 0)
                perf_metrics.false_negative_count += guardrail_metrics.get("false_negative_count", 0)
                perf_metrics.total_checks += guardrail_metrics.get("total_checks", 0)
                perf_metrics.blocked_count += guardrail_metrics.get("blocked_count", 0)
                perf_metrics.allowed_count += guardrail_metrics.get("allowed_count", 0)
        
        logger.debug(
            f"Analyzed guardrail performance for tenant {tenant_id}, domain {domain_name}: "
            f"{len(metrics)} guardrails"
        )
        
        return metrics

    def generate_recommendations(
        self,
        tenant_id: str,
        domain_name: str,
        domain_pack: Any,
        tenant_policy: TenantPolicyPack,
        performance_metrics: dict[str, GuardrailPerformanceMetrics],
    ) -> list[GuardrailRecommendation]:
        """
        Generate guardrail adjustment recommendations based on performance analysis.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            domain_pack: DomainPack instance
            tenant_policy: TenantPolicyPack instance
            performance_metrics: Dictionary of guardrail performance metrics
            
        Returns:
            List of guardrail recommendations (not auto-applied)
        """
        recommendations = []
        
        # Get guardrails (tenant policy overrides domain pack)
        guardrails = tenant_policy.custom_guardrails or domain_pack.guardrails
        
        # Analyze each guardrail
        for guardrail_id, metrics in performance_metrics.items():
            # Skip if insufficient data
            if metrics.total_checks < self.config.MIN_SAMPLE_SIZE:
                continue
            
            # Analyze false positive ratio
            false_positive_ratio = metrics.get_false_positive_ratio()
            if false_positive_ratio >= self.config.HIGH_FALSE_POSITIVE_RATIO:
                # Guardrail is too strict - suggest relaxing
                recommendation = self._generate_relaxation_recommendation(
                    tenant_id, domain_name, guardrail_id, guardrails, metrics, false_positive_ratio
                )
                if recommendation:
                    recommendations.append(recommendation)
            
            # Analyze false negative ratio
            false_negative_ratio = metrics.get_false_negative_ratio()
            if false_negative_ratio >= self.config.HIGH_FALSE_NEGATIVE_RATIO:
                # Guardrail is too lax - suggest tightening
                recommendation = self._generate_tightening_recommendation(
                    tenant_id, domain_name, guardrail_id, guardrails, metrics, false_negative_ratio
                )
                if recommendation:
                    recommendations.append(recommendation)
        
        # Attach impact analysis to each recommendation
        for recommendation in recommendations:
            self.attach_impact_analysis(recommendation, performance_metrics)
        
        # Sort by confidence (highest first)
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        
        # Persist recommendations
        self._persist_recommendations(tenant_id, domain_name, recommendations)
        
        logger.info(
            f"Generated {len(recommendations)} guardrail recommendations for tenant {tenant_id}, "
            f"domain {domain_name}"
        )
        
        return recommendations

    def _generate_relaxation_recommendation(
        self,
        tenant_id: str,
        domain_name: str,
        guardrail_id: str,
        guardrails: Guardrails,
        metrics: GuardrailPerformanceMetrics,
        false_positive_ratio: float,
    ) -> Optional[GuardrailRecommendation]:
        """
        Generate recommendation to relax a guardrail (reduce false positives).
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            guardrail_id: Guardrail identifier
            guardrails: Guardrails configuration
            metrics: Performance metrics
            false_positive_ratio: False positive ratio
            
        Returns:
            GuardrailRecommendation or None
        """
        current_config = {}
        proposed_change = {}
        reason = ""
        
        if guardrail_id == "human_approval_threshold":
            # Relax threshold (increase it, so fewer cases require approval)
            current_threshold = guardrails.human_approval_threshold
            proposed_threshold = min(1.0, current_threshold + 0.1)  # Increase by 0.1
            
            current_config = {"human_approval_threshold": current_threshold}
            proposed_change = {"human_approval_threshold": proposed_threshold}
            reason = (
                f"Human approval threshold is too strict (false positive ratio: {false_positive_ratio:.1%}). "
                f"Increase threshold from {current_threshold:.2f} to {proposed_threshold:.2f} to reduce false positives."
            )
        elif guardrail_id == "allow_lists":
            # Suggest expanding allow list (for MVP, just note the issue)
            current_config = {"allow_lists": guardrails.allow_lists}
            proposed_change = {
                "allow_lists": guardrails.allow_lists + ["<suggested_additional_items>"],
                "note": "Review and add items to allow list based on false positive patterns",
            }
            reason = (
                f"Allow list is too restrictive (false positive ratio: {false_positive_ratio:.1%}). "
                f"Consider expanding allow list based on false positive patterns."
            )
        elif guardrail_id == "block_lists":
            # Suggest reducing block list
            current_config = {"block_lists": guardrails.block_lists}
            proposed_change = {
                "block_lists": guardrails.block_lists[:-1] if guardrails.block_lists else [],
                "note": "Review and remove items from block list based on false positive patterns",
            }
            reason = (
                f"Block list is too restrictive (false positive ratio: {false_positive_ratio:.1%}). "
                f"Consider reducing block list based on false positive patterns."
            )
        else:
            # Generic relaxation recommendation
            current_config = {"guardrail_id": guardrail_id}
            proposed_change = {"relaxation": "Review guardrail criteria to reduce false positives"}
            reason = (
                f"Guardrail {guardrail_id} is too strict (false positive ratio: {false_positive_ratio:.1%}). "
                f"Consider relaxing criteria to reduce false positives."
            )
        
        # Calculate confidence based on false positive ratio and sample size
        confidence = min(1.0, false_positive_ratio * (metrics.total_checks / self.config.MIN_SAMPLE_SIZE))
        confidence = max(self.config.MIN_CONFIDENCE_THRESHOLD, confidence)
        
        recommendation = GuardrailRecommendation(
            guardrail_id=guardrail_id,
            tenant_id=tenant_id,
            current_config=current_config,
            proposed_change=proposed_change,
            reason=reason,
            impact_analysis={},  # Will be filled by attach_impact_analysis
            review_required=True,
            confidence=confidence,
            metadata={
                "false_positive_ratio": false_positive_ratio,
                "total_checks": metrics.total_checks,
                "false_positive_count": metrics.false_positive_count,
                "domain": domain_name,
            },
        )
        
        return recommendation

    def _generate_tightening_recommendation(
        self,
        tenant_id: str,
        domain_name: str,
        guardrail_id: str,
        guardrails: Guardrails,
        metrics: GuardrailPerformanceMetrics,
        false_negative_ratio: float,
    ) -> Optional[GuardrailRecommendation]:
        """
        Generate recommendation to tighten a guardrail (reduce false negatives).
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            guardrail_id: Guardrail identifier
            guardrails: Guardrails configuration
            metrics: Performance metrics
            false_negative_ratio: False negative ratio
            
        Returns:
            GuardrailRecommendation or None
        """
        current_config = {}
        proposed_change = {}
        reason = ""
        
        if guardrail_id == "human_approval_threshold":
            # Tighten threshold (decrease it, so more cases require approval)
            current_threshold = guardrails.human_approval_threshold
            proposed_threshold = max(0.0, current_threshold - 0.1)  # Decrease by 0.1
            
            current_config = {"human_approval_threshold": current_threshold}
            proposed_change = {"human_approval_threshold": proposed_threshold}
            reason = (
                f"Human approval threshold is too lenient (false negative ratio: {false_negative_ratio:.1%}). "
                f"Decrease threshold from {current_threshold:.2f} to {proposed_threshold:.2f} to reduce false negatives."
            )
        elif guardrail_id == "allow_lists":
            # Suggest reducing allow list
            current_config = {"allow_lists": guardrails.allow_lists}
            proposed_change = {
                "allow_lists": guardrails.allow_lists[:-1] if guardrails.allow_lists else [],
                "note": "Review and remove items from allow list based on false negative patterns",
            }
            reason = (
                f"Allow list is too permissive (false negative ratio: {false_negative_ratio:.1%}). "
                f"Consider reducing allow list based on false negative patterns."
            )
        elif guardrail_id == "block_lists":
            # Suggest expanding block list
            current_config = {"block_lists": guardrails.block_lists}
            proposed_change = {
                "block_lists": guardrails.block_lists + ["<suggested_additional_items>"],
                "note": "Review and add items to block list based on false negative patterns",
            }
            reason = (
                f"Block list is too permissive (false negative ratio: {false_negative_ratio:.1%}). "
                f"Consider expanding block list based on false negative patterns."
            )
        else:
            # Generic tightening recommendation
            current_config = {"guardrail_id": guardrail_id}
            proposed_change = {"tightening": "Review guardrail criteria to reduce false negatives"}
            reason = (
                f"Guardrail {guardrail_id} is too lenient (false negative ratio: {false_negative_ratio:.1%}). "
                f"Consider tightening criteria to reduce false negatives."
            )
        
        # Calculate confidence based on false negative ratio and sample size
        confidence = min(1.0, false_negative_ratio * (metrics.total_checks / self.config.MIN_SAMPLE_SIZE))
        confidence = max(self.config.MIN_CONFIDENCE_THRESHOLD, confidence)
        
        recommendation = GuardrailRecommendation(
            guardrail_id=guardrail_id,
            tenant_id=tenant_id,
            current_config=current_config,
            proposed_change=proposed_change,
            reason=reason,
            impact_analysis={},  # Will be filled by attach_impact_analysis
            review_required=True,
            confidence=confidence,
            metadata={
                "false_negative_ratio": false_negative_ratio,
                "total_checks": metrics.total_checks,
                "false_negative_count": metrics.false_negative_count,
                "violation_count": metrics.violation_count,
                "domain": domain_name,
            },
        )
        
        return recommendation

    def attach_impact_analysis(
        self,
        recommendation: GuardrailRecommendation,
        performance_metrics: dict[str, GuardrailPerformanceMetrics],
    ) -> None:
        """
        Attach impact analysis to a recommendation.
        
        Args:
            recommendation: GuardrailRecommendation to enhance
            performance_metrics: Dictionary of guardrail performance metrics
        """
        metrics = performance_metrics.get(recommendation.guardrail_id)
        if not metrics:
            # Default impact analysis if metrics not available
            recommendation.impact_analysis = {
                "estimatedFalsePositiveChange": 0.0,
                "estimatedFalseNegativeChange": 0.0,
                "confidence": recommendation.confidence,
            }
            return
        
        # Estimate impact based on current metrics
        current_fp_ratio = metrics.get_false_positive_ratio()
        current_fn_ratio = metrics.get_false_negative_ratio()
        
        # Simple heuristic: if relaxing, estimate FP reduction; if tightening, estimate FN reduction
        if "relax" in recommendation.reason.lower() or "increase" in recommendation.reason.lower():
            # Relaxing should reduce false positives
            estimated_fp_change = -current_fp_ratio * 0.3  # Estimate 30% reduction
            estimated_fn_change = current_fn_ratio * 0.1  # May slightly increase false negatives
        else:
            # Tightening should reduce false negatives
            estimated_fp_change = current_fp_ratio * 0.1  # May slightly increase false positives
            estimated_fn_change = -current_fn_ratio * 0.3  # Estimate 30% reduction
        
        recommendation.impact_analysis = {
            "estimatedFalsePositiveChange": estimated_fp_change,
            "estimatedFalseNegativeChange": estimated_fn_change,
            "confidence": recommendation.confidence,
            "currentFalsePositiveRatio": current_fp_ratio,
            "currentFalseNegativeRatio": current_fn_ratio,
            "currentAccuracy": metrics.get_accuracy(),
            "totalChecks": metrics.total_checks,
        }

    def _persist_recommendations(
        self,
        tenant_id: str,
        domain_name: str,
        recommendations: list[GuardrailRecommendation],
    ) -> None:
        """
        Persist recommendations to storage.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            recommendations: List of recommendations to persist
        """
        recommendations_file = self.storage_dir / f"{tenant_id}_{domain_name}_guardrail_recommendations.jsonl"
        
        try:
            with open(recommendations_file, "a", encoding="utf-8") as f:
                for recommendation in recommendations:
                    recommendation_dict = recommendation.model_dump(by_alias=True, mode="json")
                    f.write(json.dumps(recommendation_dict, default=str) + "\n")
            
            logger.debug(
                f"Persisted {len(recommendations)} guardrail recommendations to {recommendations_file}"
            )
        except Exception as e:
            logger.error(f"Failed to persist guardrail recommendations: {e}", exc_info=True)

    def load_recommendations(
        self, tenant_id: str, domain_name: str
    ) -> list[GuardrailRecommendation]:
        """
        Load persisted recommendations.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            
        Returns:
            List of guardrail recommendations
        """
        recommendations_file = self.storage_dir / f"{tenant_id}_{domain_name}_guardrail_recommendations.jsonl"
        
        recommendations = []
        
        if not recommendations_file.exists():
            return recommendations
        
        try:
            with open(recommendations_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        recommendation = GuardrailRecommendation.model_validate(data)
                        recommendations.append(recommendation)
                    except Exception as e:
                        logger.warning(f"Failed to parse recommendation: {e}")
                        continue
        except Exception as e:
            logger.error(f"Failed to load recommendations: {e}", exc_info=True)
        
        return recommendations

