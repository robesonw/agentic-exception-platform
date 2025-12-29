"""
Similarity services for Copilot functionality.

This package provides services for finding similar exceptions,
resolving cross-references, and generating similarity-based recommendations.
"""

from .similar_exceptions import SimilarExceptionsFinder, SimilarException

__all__ = [
    "SimilarExceptionsFinder",
    "SimilarException",
]