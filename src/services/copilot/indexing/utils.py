"""
Utilities for Phase 13 Copilot Indexing.

Provides stable key generation and content hashing functions:
- stable_chunk_key for consistent chunk identification
- content_hash for deduplication and change detection
- Tenant-aware key builders that maintain isolation

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2
- .github/issue_template/phase13-copilot-intelligence-issues.md P13-6, P13-7
"""

import hashlib
import json
from typing import Any, Optional

from src.infrastructure.db.models import CopilotDocumentSourceType


def stable_chunk_key(
    tenant_id: str,
    source_type: CopilotDocumentSourceType,
    source_id: str,
    chunk_id: str,
    source_version: Optional[str] = None,
) -> str:
    """
    Generate a stable chunk key for consistent identification.
    
    The key ensures:
    - Tenant isolation (tenant_id prefix)
    - Source type classification
    - Unique identification within source
    - Version awareness for cache invalidation
    
    Args:
        tenant_id: Tenant identifier for isolation
        source_type: Type of source document
        source_id: Unique identifier of source document
        chunk_id: Unique identifier of chunk within document
        source_version: Optional version for cache invalidation
    
    Returns:
        Stable string key for chunk identification
        
    Example:
        >>> stable_chunk_key(
        ...     "TENANT_001",
        ...     CopilotDocumentSourceType.POLICY_DOC,
        ...     "SOP-FIN-001",
        ...     "chunk-0"
        ... )
        'TENANT_001:policy_doc:SOP-FIN-001:chunk-0'
    """
    components = [
        tenant_id,
        source_type.value,
        source_id,
        chunk_id,
    ]
    
    if source_version:
        components.append(f"v{source_version}")
    
    return ":".join(components)


def content_hash(
    content: str,
    algorithm: str = "sha256",
    encoding: str = "utf-8",
) -> str:
    """
    Generate a stable hash of content for deduplication.
    
    Args:
        content: Text content to hash
        algorithm: Hash algorithm to use (default: sha256)
        encoding: Text encoding (default: utf-8)
    
    Returns:
        Hex-encoded hash string
        
    Example:
        >>> content_hash("Hello, world!")
        'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
    """
    if not content:
        return ""
    
    hasher = hashlib.new(algorithm)
    hasher.update(content.encode(encoding))
    return hasher.hexdigest()


def metadata_hash(
    metadata: dict[str, Any],
    algorithm: str = "sha256",
) -> str:
    """
    Generate a stable hash of metadata for change detection.
    
    Args:
        metadata: Dictionary of metadata to hash
        algorithm: Hash algorithm to use (default: sha256)
    
    Returns:
        Hex-encoded hash string
        
    Example:
        >>> metadata_hash({"title": "Test", "version": "1.0"})
        'e8b7f1f7bc50eb2b3e2b2b7b...'  # actual hash
    """
    if not metadata:
        return ""
    
    # Sort keys for stable serialization
    normalized = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return content_hash(normalized, algorithm)


def document_fingerprint(
    content: str,
    metadata: Optional[dict[str, Any]] = None,
    source_version: Optional[str] = None,
) -> str:
    """
    Generate a comprehensive fingerprint for document change detection.
    
    Combines content hash, metadata hash, and version for complete
    change tracking. Useful for incremental indexing decisions.
    
    Args:
        content: Document content
        metadata: Optional metadata dictionary
        source_version: Optional version string
    
    Returns:
        Composite fingerprint string
        
    Example:
        >>> document_fingerprint(
        ...     "Document content",
        ...     {"title": "Test"},
        ...     "1.0"
        ... )
        'content:abc123...;metadata:def456...;version:1.0'
    """
    parts = [f"content:{content_hash(content)}"]
    
    if metadata:
        parts.append(f"metadata:{metadata_hash(metadata)}")
    
    if source_version:
        parts.append(f"version:{source_version}")
    
    return ";".join(parts)


def validate_tenant_id(tenant_id: str) -> bool:
    """
    Validate tenant ID format for security.
    
    Args:
        tenant_id: Tenant identifier to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not tenant_id or not isinstance(tenant_id, str):
        return False
    
    # Basic validation: non-empty, reasonable length, no special chars
    if len(tenant_id) == 0 or len(tenant_id) > 255:
        return False
    
    # Allow alphanumeric, hyphens, underscores
    import re
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", tenant_id))


def sanitize_chunk_id(chunk_id: str) -> str:
    """
    Sanitize chunk ID for safe key generation.
    
    Args:
        chunk_id: Raw chunk identifier
    
    Returns:
        Sanitized chunk identifier
    """
    if not chunk_id:
        return "unknown"
    
    # Replace problematic characters with safe alternatives
    sanitized = chunk_id.replace(":", "-").replace("/", "-").replace(" ", "_")
    
    # Limit length to prevent key bloat
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    
    return sanitized
