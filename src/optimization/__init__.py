"""
Optimization module for metrics-driven optimization engine.

Phase 3: Central engine that consumes metrics and produces optimization recommendations.
"""

from src.optimization.engine import (
    OptimizationEngine,
    OptimizationEngineError,
    OptimizationRecommendation,
    OptimizationSignal,
)

__all__ = [
    "OptimizationEngine",
    "OptimizationEngineError",
    "OptimizationRecommendation",
    "OptimizationSignal",
]

