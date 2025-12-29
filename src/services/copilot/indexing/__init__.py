"""
Phase 13 Copilot Indexing Foundation.

Provides core indexing infrastructure for vector-based document search:
- BaseIndexer interface for consistent indexing operations
- PolicyDocsIndexer for indexing policy documents from packs
- PlaybookIndexer for indexing playbook definitions from packs
- IndexingResult and IndexJobStatus for tracking operations
- Utilities for stable key generation and content hashing

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2
- .github/issue_template/phase13-copilot-intelligence-issues.md P13-4 through P13-8
"""

from .base import BaseIndexer, IndexingError, TenantIsolationError
from .policy_docs_indexer import PolicyDoc, PolicyDocsIndexer
from .playbook_indexer import PlaybookDefinition, PlaybookIndexer
from .resolved_exceptions_indexer import ResolvedExceptionDoc, ResolvedExceptionsIndexer
from .types import IndexingResult, IndexJobStatus
from .utils import (
    content_hash,
    document_fingerprint,
    metadata_hash,
    stable_chunk_key,
    sanitize_chunk_id,
    validate_tenant_id,
)

__all__ = [
    # Base classes
    "BaseIndexer",
    "IndexingError",
    "TenantIsolationError",
    # Concrete indexers
    "PolicyDocsIndexer",
    "PolicyDoc",
    "PlaybookIndexer",
    "PlaybookDefinition",
    "ResolvedExceptionsIndexer",
    "ResolvedExceptionDoc",
    # Data types
    "IndexingResult",
    "IndexJobStatus",
    # Utilities
    "stable_chunk_key",
    "content_hash",
    "metadata_hash",
    "document_fingerprint",
    "sanitize_chunk_id",
    "validate_tenant_id",
]
