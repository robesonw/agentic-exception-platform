"""
Metrics-Driven Optimization Engine for Phase 3.

Central engine that consumes metrics (success rates, MTTR, false pos/neg) and
produces optimization recommendations across policies, severity rules, playbooks, and guardrails.

Safety:
- Recommendations only, never auto-applied
- All recommendations require human review and approval

Matches specification from phase3-mvp-issues.md P3-11.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class OptimizationSignal:
    """
    Optimization signal from a metric source.
    
    Represents a single metric that indicates an optimization opportunity.
    """

    source: str  # Source of the signal (e.g., 'policy_learning', 'severity_recommender')
    metric_type: str  # Type of metric (e.g., 'success_rate', 'mttr', 'false_positive_rate')
    current_value: float  # Current value of the metric
    target_value: Optional[float] = None  # Target or optimal value for the metric
    tenant_id: str = ""  # Tenant identifier
    domain: str = ""  # Domain name identifier
    entity_id: Optional[str] = None  # Optional entity identifier (e.g., rule_id, playbook_id)
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional metadata about the signal


class OptimizationRecommendation(BaseModel):
    """
    Unified optimization recommendation.
    
    Normalizes recommendations from all sources (policy, severity, playbook, guardrail)
    into a common format.
    """

    id: str = Field(..., description="Unique identifier for the recommendation")
    tenant_id: str = Field(..., description="Tenant identifier")
    domain: str = Field(..., description="Domain name identifier")
    category: str = Field(
        ..., description="Category of recommendation (policy, severity, playbook, guardrail)"
    )
    description: str = Field(..., description="Human-readable description of the recommendation")
    impact_estimate: str = Field(..., description="Estimated impact of applying the recommendation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the recommendation")
    related_entities: list[str] = Field(
        default_factory=list, description="List of related entity IDs (rule_ids, playbook_ids, etc.)"
    )
    source: str = Field(..., description="Source of the recommendation (e.g., 'policy_learning')")
    source_suggestion_id: Optional[str] = Field(
        None, description="ID of the original suggestion from the source system"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class OptimizationEngineError(Exception):
    """Raised when optimization engine operations fail."""

    pass


class OptimizationEngine:
    """
    Metrics-driven optimization engine.
    
    Central engine that:
    - Collects optimization signals from various sources
    - Generates unified optimization recommendations
    - Normalizes recommendations from different sources
    - Persists recommendations for review
    
    Responsibilities:
    - Collect signals from policy learning, severity recommender, playbook recommender, guardrail analysis
    - Generate unified recommendations
    - Store recommendations for human review
    """

    def __init__(self, storage_dir: str = "./runtime/optimization"):
        """
        Initialize OptimizationEngine.
        
        Args:
            storage_dir: Directory for storing optimization recommendations
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Optional recommenders (injected via dependency injection)
        self.policy_learning: Optional[Any] = None
        self.severity_recommender: Optional[Any] = None
        self.playbook_recommender: Optional[Any] = None
        self.guardrail_recommender: Optional[Any] = None  # Phase 3: P3-10

    def set_recommenders(
        self,
        policy_learning: Optional[Any] = None,
        severity_recommender: Optional[Any] = None,
        playbook_recommender: Optional[Any] = None,
        guardrail_recommender: Optional[Any] = None,
    ) -> None:
        """
        Set recommender instances for dependency injection.
        
        Phase 3: Enhanced with guardrail recommender (P3-10).
        
        Args:
            policy_learning: Optional PolicyLearning instance
            severity_recommender: Optional SeverityRecommender instance
            playbook_recommender: Optional PlaybookRecommender instance
            guardrail_recommender: Optional GuardrailRecommender instance (P3-10)
        """
        self.policy_learning = policy_learning
        self.severity_recommender = severity_recommender
        self.playbook_recommender = playbook_recommender
        self.guardrail_recommender = guardrail_recommender

    def collect_signals(
        self, tenant_id: str, domain: str
    ) -> list[OptimizationSignal]:
        """
        Collect optimization signals from all available sources.
        
        Pulls signals from:
        - Policy learning metrics
        - Severity recommender metrics
        - Playbook recommender metrics
        - Guardrail analyzer metrics
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            
        Returns:
            List of optimization signals
        """
        signals = []
        
        # Collect signals from policy learning
        if self.policy_learning:
            try:
                policy_signals = self._collect_policy_signals(tenant_id, domain)
                signals.extend(policy_signals)
            except Exception as e:
                logger.warning(f"Failed to collect policy signals: {e}")
        
        # Collect signals from severity recommender
        if self.severity_recommender:
            try:
                severity_signals = self._collect_severity_signals(tenant_id, domain)
                signals.extend(severity_signals)
            except Exception as e:
                logger.warning(f"Failed to collect severity signals: {e}")
        
        # Collect signals from playbook recommender
        if self.playbook_recommender:
            try:
                playbook_signals = self._collect_playbook_signals(tenant_id, domain)
                signals.extend(playbook_signals)
            except Exception as e:
                logger.warning(f"Failed to collect playbook signals: {e}")
        
        # Collect signals from guardrail recommender (if available) - Phase 3: P3-10
        if self.guardrail_recommender:
            try:
                guardrail_signals = self._collect_guardrail_signals(tenant_id, domain)
                signals.extend(guardrail_signals)
            except Exception as e:
                logger.warning(f"Failed to collect guardrail signals: {e}")
        
        logger.info(
            f"Collected {len(signals)} optimization signals for tenant {tenant_id}, domain {domain}"
        )
        
        return signals

    def generate_recommendations(
        self, tenant_id: str, domain: str
    ) -> list[OptimizationRecommendation]:
        """
        Generate unified optimization recommendations from all sources.
        
        Calls into:
        - policy_learning.suggest_policy_improvements(...)
        - severity_recommender.analyze_severity_patterns(...)
        - playbook_recommender.analyze_resolutions(...)
        - guardrail_analyzer.analyze_guardrail_outcomes(...)
        
        Normalizes all into OptimizationRecommendation objects.
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            
        Returns:
            List of unified optimization recommendations
        """
        recommendations = []
        recommendation_counter = 0
        
        # Generate recommendations from policy learning
        if self.policy_learning:
            try:
                policy_suggestions = self.policy_learning.suggest_policy_improvements(tenant_id)
                for suggestion in policy_suggestions:
                    recommendation_counter += 1
                    rec = OptimizationRecommendation(
                        id=f"{tenant_id}_{domain}_policy_{recommendation_counter}",
                        tenant_id=tenant_id,
                        domain=domain,
                        category="policy",
                        description=suggestion.proposed_change,
                        impact_estimate=suggestion.impact_estimate,
                        confidence=suggestion.confidence,
                        related_entities=[suggestion.rule_id],
                        source="policy_learning",
                        source_suggestion_id=suggestion.rule_id,
                        metadata=suggestion.metrics,
                    )
                    recommendations.append(rec)
            except Exception as e:
                logger.warning(f"Failed to generate policy recommendations: {e}")
        
        # Generate recommendations from severity recommender
        if self.severity_recommender:
            try:
                severity_suggestions = self.severity_recommender.analyze_severity_patterns(
                    tenant_id, domain
                )
                for i, suggestion in enumerate(severity_suggestions):
                    recommendation_counter += 1
                    rec = OptimizationRecommendation(
                        id=f"{tenant_id}_{domain}_severity_{recommendation_counter}",
                        tenant_id=tenant_id,
                        domain=domain,
                        category="severity",
                        description=suggestion.pattern_description,
                        impact_estimate=f"Confidence: {suggestion.confidence_score:.1%}",
                        confidence=suggestion.confidence_score,
                        related_entities=suggestion.example_exceptions[:5],  # Limit to 5
                        source="severity_recommender",
                        source_suggestion_id=f"severity_suggestion_{i}",
                        metadata=suggestion.supporting_metrics,
                    )
                    recommendations.append(rec)
            except Exception as e:
                logger.warning(f"Failed to generate severity recommendations: {e}")
        
        # Generate recommendations from playbook recommender
        if self.playbook_recommender:
            try:
                playbook_suggestions = self.playbook_recommender.analyze_resolutions(
                    tenant_id, domain
                )
                for i, suggestion in enumerate(playbook_suggestions):
                    recommendation_counter += 1
                    rec = OptimizationRecommendation(
                        id=f"{tenant_id}_{domain}_playbook_{recommendation_counter}",
                        tenant_id=tenant_id,
                        domain=domain,
                        category="playbook",
                        description=suggestion.rationale,
                        impact_estimate=f"Predicted effectiveness: {suggestion.effectiveness_prediction:.1%}",
                        confidence=suggestion.effectiveness_prediction,
                        related_entities=suggestion.supporting_examples[:5],  # Limit to 5
                        source="playbook_recommender",
                        source_suggestion_id=f"playbook_suggestion_{i}",
                        metadata=suggestion.supporting_metrics,
                    )
                    recommendations.append(rec)
            except Exception as e:
                logger.warning(f"Failed to generate playbook recommendations: {e}")
        
        # Phase 3: Generate recommendations from guardrail recommender (if available) - P3-10
        if self.guardrail_recommender:
            try:
                guardrail_suggestions = self._generate_guardrail_recommendations(
                    tenant_id, domain
                )
                recommendations.extend(guardrail_suggestions)
            except Exception as e:
                logger.warning(f"Failed to generate guardrail recommendations: {e}")
        
        # Sort by confidence (highest first)
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        
        # Persist recommendations
        self._persist_recommendations(tenant_id, domain, recommendations)
        
        logger.info(
            f"Generated {len(recommendations)} optimization recommendations for tenant {tenant_id}, "
            f"domain {domain}"
        )
        
        return recommendations

    def _collect_policy_signals(
        self, tenant_id: str, domain: str
    ) -> list[OptimizationSignal]:
        """
        Collect optimization signals from policy learning.
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            
        Returns:
            List of optimization signals
        """
        signals = []
        
        # Access policy learning rule outcomes
        if hasattr(self.policy_learning, "_rule_outcomes"):
            rule_outcomes = self.policy_learning._rule_outcomes.get(tenant_id, {})
            
            for rule_id, outcome in rule_outcomes.items():
                if outcome.total_count < 3:
                    continue
                
                total = outcome.total_count
                success_rate = outcome.success_count / total if total > 0 else 0
                false_positive_rate = outcome.false_positive_count / total if total > 0 else 0
                false_negative_rate = outcome.false_negative_count / total if total > 0 else 0
                
                # Signal: Low success rate
                if success_rate < 0.5:
                    signals.append(
                        OptimizationSignal(
                            source="policy_learning",
                            metric_type="success_rate",
                            current_value=success_rate,
                            target_value=0.8,
                            tenant_id=tenant_id,
                            domain=domain,
                            entity_id=rule_id,
                            metadata={"total_count": total, "failure_count": outcome.failure_count},
                        )
                    )
                
                # Signal: High false positive rate
                if false_positive_rate > 0.2:
                    signals.append(
                        OptimizationSignal(
                            source="policy_learning",
                            metric_type="false_positive_rate",
                            current_value=false_positive_rate,
                            target_value=0.1,
                            tenant_id=tenant_id,
                            domain=domain,
                            entity_id=rule_id,
                            metadata={"false_positive_count": outcome.false_positive_count},
                        )
                    )
                
                # Signal: High false negative rate
                if false_negative_rate > 0.2:
                    signals.append(
                        OptimizationSignal(
                            source="policy_learning",
                            metric_type="false_negative_rate",
                            current_value=false_negative_rate,
                            target_value=0.1,
                            tenant_id=tenant_id,
                            domain=domain,
                            entity_id=rule_id,
                            metadata={"false_negative_count": outcome.false_negative_count},
                        )
                    )
        
        return signals

    def _collect_severity_signals(
        self, tenant_id: str, domain: str
    ) -> list[OptimizationSignal]:
        """
        Collect optimization signals from severity recommender.
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            
        Returns:
            List of optimization signals
        """
        signals = []
        
        # For MVP, severity signals are derived from suggestions
        # In production, would analyze historical severity patterns directly
        try:
            severity_suggestions = self.severity_recommender.analyze_severity_patterns(
                tenant_id, domain
            )
            
            for suggestion in severity_suggestions:
                # Signal: High confidence severity rule suggestion
                if suggestion.confidence_score > 0.7:
                    signals.append(
                        OptimizationSignal(
                            source="severity_recommender",
                            metric_type="severity_rule_confidence",
                            current_value=suggestion.confidence_score,
                            target_value=0.9,
                            tenant_id=tenant_id,
                            domain=domain,
                            entity_id=suggestion.candidate_rule.condition,
                            metadata={
                                "example_count": len(suggestion.example_exceptions),
                                "pattern": suggestion.pattern_description,
                            },
                        )
                    )
        except Exception as e:
            logger.debug(f"Could not collect severity signals: {e}")
        
        return signals

    def _collect_playbook_signals(
        self, tenant_id: str, domain: str
    ) -> list[OptimizationSignal]:
        """
        Collect optimization signals from playbook recommender.
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            
        Returns:
            List of optimization signals
        """
        signals = []
        
        # For MVP, playbook signals are derived from suggestions
        # In production, would analyze playbook performance metrics directly
        try:
            playbook_suggestions = self.playbook_recommender.analyze_resolutions(
                tenant_id, domain
            )
            
            for suggestion in playbook_suggestions:
                # Signal: High effectiveness prediction
                if suggestion.effectiveness_prediction > 0.7:
                    signals.append(
                        OptimizationSignal(
                            source="playbook_recommender",
                            metric_type="playbook_effectiveness",
                            current_value=suggestion.effectiveness_prediction,
                            target_value=0.9,
                            tenant_id=tenant_id,
                            domain=domain,
                            entity_id=suggestion.candidate_playbook.exception_type,
                            metadata={
                                "example_count": len(suggestion.supporting_examples),
                                "suggestion_type": suggestion.suggestion_type,
                            },
                        )
                    )
        except Exception as e:
            logger.debug(f"Could not collect playbook signals: {e}")
        
        return signals

    def _collect_guardrail_signals(
        self, tenant_id: str, domain: str
    ) -> list[OptimizationSignal]:
        """
        Collect optimization signals from guardrail recommender.
        
        Phase 3: Enhanced with GuardrailRecommender integration (P3-10).
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            
        Returns:
            List of optimization signals
        """
        signals = []
        
        # Phase 3: Collect signals from guardrail recommender (P3-10)
        if self.guardrail_recommender:
            try:
                # Load recommendations to extract signals
                recommendations = self.guardrail_recommender.load_recommendations(tenant_id, domain)
                
                for rec in recommendations:
                    # Extract false positive/negative ratios from impact analysis
                    impact = rec.impact_analysis
                    fp_ratio = impact.get("currentFalsePositiveRatio", 0.0)
                    fn_ratio = impact.get("currentFalseNegativeRatio", 0.0)
                    
                    # Signal: High false positive rate
                    if fp_ratio > 0.2:
                        signals.append(
                            OptimizationSignal(
                                source="guardrail_recommender",
                                metric_type="false_positive_rate",
                                current_value=fp_ratio,
                                target_value=0.1,
                                tenant_id=tenant_id,
                                domain=domain,
                                entity_id=rec.guardrail_id,
                                metadata={"guardrail_id": rec.guardrail_id, "confidence": rec.confidence},
                            )
                        )
                    
                    # Signal: High false negative rate
                    if fn_ratio > 0.2:
                        signals.append(
                            OptimizationSignal(
                                source="guardrail_recommender",
                                metric_type="false_negative_rate",
                                current_value=fn_ratio,
                                target_value=0.1,
                                tenant_id=tenant_id,
                                domain=domain,
                                entity_id=rec.guardrail_id,
                                metadata={"guardrail_id": rec.guardrail_id, "confidence": rec.confidence},
                            )
                        )
            except Exception as e:
                logger.debug(f"Could not collect guardrail signals: {e}")
        
        return signals

    def _generate_guardrail_recommendations(
        self, tenant_id: str, domain: str
    ) -> list[OptimizationRecommendation]:
        """
        Generate guardrail optimization recommendations.
        
        Phase 3: Enhanced with GuardrailRecommender integration (P3-10).
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            
        Returns:
            List of guardrail recommendations
        """
        recommendations = []
        
        # Phase 3: Generate recommendations from guardrail recommender (P3-10)
        if self.guardrail_recommender:
            try:
                # Load guardrail recommendations
                guardrail_suggestions = self.guardrail_recommender.load_recommendations(tenant_id, domain)
                
                # Convert to OptimizationRecommendation format
                for i, suggestion in enumerate(guardrail_suggestions):
                    rec = OptimizationRecommendation(
                        id=f"{tenant_id}_{domain}_guardrail_{i+1}",
                        tenant_id=tenant_id,
                        domain=domain,
                        category="guardrail",
                        description=suggestion.reason,
                        impact_estimate=(
                            f"FP change: {suggestion.impact_analysis.get('estimatedFalsePositiveChange', 0.0):.1%}, "
                            f"FN change: {suggestion.impact_analysis.get('estimatedFalseNegativeChange', 0.0):.1%}"
                        ),
                        confidence=suggestion.confidence,
                        related_entities=[suggestion.guardrail_id],
                        source="guardrail_recommender",
                        source_suggestion_id=suggestion.guardrail_id,
                        metadata={
                            "current_config": suggestion.current_config,
                            "proposed_change": suggestion.proposed_change,
                            "impact_analysis": suggestion.impact_analysis,
                        },
                    )
                    recommendations.append(rec)
            except Exception as e:
                logger.debug(f"Could not generate guardrail recommendations: {e}")
        
        return recommendations

    def _persist_recommendations(
        self,
        tenant_id: str,
        domain: str,
        recommendations: list[OptimizationRecommendation],
    ) -> None:
        """
        Persist optimization recommendations to tenant/domain-specific JSONL file.
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            recommendations: List of recommendations to persist
        """
        recommendations_file = (
            self.storage_dir / f"{tenant_id}_{domain}_recommendations.jsonl"
        )
        
        # Append each recommendation as a JSONL line
        with open(recommendations_file, "a", encoding="utf-8") as f:
            for recommendation in recommendations:
                recommendation_dict = recommendation.model_dump()
                recommendation_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(recommendation_dict, default=str) + "\n")
        
        logger.debug(
            f"Persisted {len(recommendations)} optimization recommendations to {recommendations_file}"
        )

