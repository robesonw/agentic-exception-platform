"""
Optimization Service for Phase 3.

Service entry point for running periodic optimization analysis.
This will be used by ops/cron or admin API (Phase 3+).

Matches specification from phase3-mvp-issues.md P3-11.
"""

import logging
from typing import Any, Optional

from src.optimization.engine import OptimizationEngine

logger = logging.getLogger(__name__)


class OptimizationService:
    """
    Optimization service for periodic optimization runs.
    
    Provides service entry point for running optimization analysis
    on a schedule (via cron or admin API).
    """

    def __init__(
        self,
        optimization_engine: Optional[OptimizationEngine] = None,
    ):
        """
        Initialize OptimizationService.
        
        Args:
            optimization_engine: Optional OptimizationEngine instance
        """
        self.optimization_engine = optimization_engine or OptimizationEngine()

    def run_periodic_optimization(
        self,
        tenant_id: str,
        domain: str,
        policy_learning: Optional[Any] = None,
        severity_recommender: Optional[Any] = None,
        playbook_recommender: Optional[Any] = None,
        guardrail_analyzer: Optional[Any] = None,
    ) -> None:
        """
        Run periodic optimization analysis for a tenant and domain.
        
        This method:
        1. Sets up recommenders in the optimization engine
        2. Collects optimization signals
        3. Generates unified recommendations
        4. Persists recommendations for review
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            policy_learning: Optional PolicyLearning instance
            severity_recommender: Optional SeverityRecommender instance
            playbook_recommender: Optional PlaybookRecommender instance
            guardrail_analyzer: Optional guardrail analyzer instance
        """
        try:
            # Set recommenders
            self.optimization_engine.set_recommenders(
                policy_learning=policy_learning,
                severity_recommender=severity_recommender,
                playbook_recommender=playbook_recommender,
                guardrail_analyzer=guardrail_analyzer,
            )
            
            # Collect signals
            signals = self.optimization_engine.collect_signals(tenant_id, domain)
            logger.info(
                f"Collected {len(signals)} optimization signals for tenant {tenant_id}, domain {domain}"
            )
            
            # Generate recommendations
            recommendations = self.optimization_engine.generate_recommendations(
                tenant_id, domain
            )
            logger.info(
                f"Generated {len(recommendations)} optimization recommendations for tenant {tenant_id}, "
                f"domain {domain}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to run periodic optimization for tenant {tenant_id}, domain {domain}: {e}"
            )
            raise


def run_periodic_optimization(
    tenant_id: str,
    domain: str,
    policy_learning: Optional[Any] = None,
    severity_recommender: Optional[Any] = None,
    playbook_recommender: Optional[Any] = None,
    guardrail_analyzer: Optional[Any] = None,
) -> None:
    """
    Convenience function to run periodic optimization.
    
    Args:
        tenant_id: Tenant identifier
        domain: Domain name identifier
        policy_learning: Optional PolicyLearning instance
        severity_recommender: Optional SeverityRecommender instance
        playbook_recommender: Optional PlaybookRecommender instance
        guardrail_analyzer: Optional guardrail analyzer instance
    """
    service = OptimizationService()
    service.run_periodic_optimization(
        tenant_id=tenant_id,
        domain=domain,
        policy_learning=policy_learning,
        severity_recommender=severity_recommender,
        playbook_recommender=playbook_recommender,
        guardrail_analyzer=guardrail_analyzer,
    )

