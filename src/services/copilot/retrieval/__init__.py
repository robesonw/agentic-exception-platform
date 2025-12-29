"""
Copilot Retrieval Services for Phase 13.

Provides evidence-based retrieval with tenant isolation and pgvector similarity search.
"""

from .retrieval_service import EvidenceItem, RetrievalService

__all__ = ["EvidenceItem", "RetrievalService"]