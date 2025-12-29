"""
Unit tests for Phase 13 Copilot Indexing utilities.

Tests stable key generation and content hashing functions for:
- Consistent chunk identification across runs
- Tenant isolation in key generation
- Content deduplication via hashing
- Security and validation helpers

References:
- src/services/copilot/indexing/utils.py
- .github/issue_template/phase13-copilot-intelligence-issues.md P13-6, P13-7
"""

import pytest

from src.infrastructure.db.models import CopilotDocumentSourceType
from src.services.copilot.indexing.utils import (
    content_hash,
    document_fingerprint,
    metadata_hash,
    sanitize_chunk_id,
    stable_chunk_key,
    validate_tenant_id,
)


class TestStableChunkKey:
    """Tests for stable_chunk_key function."""

    def test_basic_key_generation(self):
        """Test basic chunk key generation."""
        key = stable_chunk_key(
            tenant_id="TENANT_001",
            source_type=CopilotDocumentSourceType.POLICY_DOC,
            source_id="SOP-FIN-001",
            chunk_id="chunk-0",
        )
        
        expected = "TENANT_001:policy_doc:SOP-FIN-001:chunk-0"
        assert key == expected

    def test_key_with_version(self):
        """Test chunk key generation with version."""
        key = stable_chunk_key(
            tenant_id="TENANT_001",
            source_type=CopilotDocumentSourceType.POLICY_DOC,
            source_id="SOP-FIN-001",
            chunk_id="chunk-0",
            source_version="1.2.3",
        )
        
        expected = "TENANT_001:policy_doc:SOP-FIN-001:chunk-0:v1.2.3"
        assert key == expected

    def test_different_source_types(self):
        """Test key generation for different source types."""
        base_params = {
            "tenant_id": "TENANT_001",
            "source_id": "DOC-001",
            "chunk_id": "chunk-0",
        }
        
        # Test each source type
        policy_key = stable_chunk_key(
            source_type=CopilotDocumentSourceType.POLICY_DOC,
            **base_params,
        )
        exception_key = stable_chunk_key(
            source_type=CopilotDocumentSourceType.RESOLVED_EXCEPTION,
            **base_params,
        )
        audit_key = stable_chunk_key(
            source_type=CopilotDocumentSourceType.AUDIT_EVENT,
            **base_params,
        )
        
        # Keys should be different
        assert policy_key != exception_key
        assert exception_key != audit_key
        assert audit_key != policy_key
        
        # But contain expected source type values
        assert "policy_doc" in policy_key
        assert "resolved_exception" in exception_key
        assert "audit_event" in audit_key

    def test_tenant_isolation_in_keys(self):
        """Test that different tenants generate different keys."""
        base_params = {
            "source_type": CopilotDocumentSourceType.POLICY_DOC,
            "source_id": "SOP-FIN-001",
            "chunk_id": "chunk-0",
        }
        
        key_1 = stable_chunk_key(tenant_id="TENANT_001", **base_params)
        key_2 = stable_chunk_key(tenant_id="TENANT_002", **base_params)
        
        assert key_1 != key_2
        assert key_1.startswith("TENANT_001:")
        assert key_2.startswith("TENANT_002:")

    def test_key_stability(self):
        """Test that keys are stable across multiple calls."""
        params = {
            "tenant_id": "TENANT_001",
            "source_type": CopilotDocumentSourceType.POLICY_DOC,
            "source_id": "SOP-FIN-001",
            "chunk_id": "chunk-0",
            "source_version": "1.0",
        }
        
        # Generate same key multiple times
        keys = [stable_chunk_key(**params) for _ in range(5)]
        
        # All should be identical
        assert len(set(keys)) == 1
        assert all(key == keys[0] for key in keys)


class TestContentHash:
    """Tests for content_hash function."""

    def test_basic_content_hashing(self):
        """Test basic content hashing."""
        content = "Hello, world!"
        hash_value = content_hash(content)
        
        # Should return a non-empty string
        assert isinstance(hash_value, str)
        assert len(hash_value) > 0
        
        # Should be consistent
        assert content_hash(content) == hash_value

    def test_different_content_different_hash(self):
        """Test that different content produces different hashes."""
        hash_1 = content_hash("Content 1")
        hash_2 = content_hash("Content 2")
        
        assert hash_1 != hash_2

    def test_empty_content(self):
        """Test handling of empty content."""
        assert content_hash("") == ""
        assert content_hash(None) == ""  # Should handle None gracefully

    def test_hash_algorithms(self):
        """Test different hash algorithms."""
        content = "Test content"
        
        sha256_hash = content_hash(content, algorithm="sha256")
        md5_hash = content_hash(content, algorithm="md5")
        
        # Should be different algorithms
        assert sha256_hash != md5_hash
        
        # SHA256 should be longer
        assert len(sha256_hash) > len(md5_hash)

    def test_hash_stability(self):
        """Test that hashes are stable across multiple calls."""
        content = "Stable content for testing"
        
        hashes = [content_hash(content) for _ in range(5)]
        
        # All should be identical
        assert len(set(hashes)) == 1
        assert all(h == hashes[0] for h in hashes)


class TestMetadataHash:
    """Tests for metadata_hash function."""

    def test_basic_metadata_hashing(self):
        """Test basic metadata hashing."""
        metadata = {"title": "Test Document", "version": "1.0"}
        hash_value = metadata_hash(metadata)
        
        assert isinstance(hash_value, str)
        assert len(hash_value) > 0

    def test_empty_metadata(self):
        """Test handling of empty metadata."""
        assert metadata_hash({}) == ""
        assert metadata_hash(None) == ""

    def test_key_order_independence(self):
        """Test that key order doesn't affect hash."""
        metadata_1 = {"title": "Test", "version": "1.0", "author": "John"}
        metadata_2 = {"version": "1.0", "author": "John", "title": "Test"}
        
        hash_1 = metadata_hash(metadata_1)
        hash_2 = metadata_hash(metadata_2)
        
        assert hash_1 == hash_2

    def test_different_metadata_different_hash(self):
        """Test that different metadata produces different hashes."""
        metadata_1 = {"title": "Doc 1", "version": "1.0"}
        metadata_2 = {"title": "Doc 2", "version": "1.0"}
        
        hash_1 = metadata_hash(metadata_1)
        hash_2 = metadata_hash(metadata_2)
        
        assert hash_1 != hash_2


class TestDocumentFingerprint:
    """Tests for document_fingerprint function."""

    def test_content_only_fingerprint(self):
        """Test fingerprint with content only."""
        content = "Document content"
        fingerprint = document_fingerprint(content)
        
        assert fingerprint.startswith("content:")
        assert "metadata:" not in fingerprint
        assert "version:" not in fingerprint

    def test_full_fingerprint(self):
        """Test fingerprint with all components."""
        content = "Document content"
        metadata = {"title": "Test"}
        version = "1.0"
        
        fingerprint = document_fingerprint(content, metadata, version)
        
        assert "content:" in fingerprint
        assert "metadata:" in fingerprint
        assert "version:1.0" in fingerprint

    def test_fingerprint_stability(self):
        """Test that fingerprints are stable."""
        content = "Stable content"
        metadata = {"title": "Stable doc"}
        version = "1.0"
        
        fingerprints = [
            document_fingerprint(content, metadata, version)
            for _ in range(3)
        ]
        
        assert len(set(fingerprints)) == 1

    def test_fingerprint_change_detection(self):
        """Test that fingerprints change when content changes."""
        base_params = {"metadata": {"title": "Test"}, "source_version": "1.0"}
        
        fp1 = document_fingerprint("Content 1", **base_params)
        fp2 = document_fingerprint("Content 2", **base_params)
        
        assert fp1 != fp2


class TestValidateTenantId:
    """Tests for validate_tenant_id function."""

    def test_valid_tenant_ids(self):
        """Test validation of valid tenant IDs."""
        valid_ids = [
            "TENANT_001",
            "tenant-123",
            "org_dept_001",
            "ABC123",
            "simple",
        ]
        
        for tenant_id in valid_ids:
            assert validate_tenant_id(tenant_id), f"Should be valid: {tenant_id}"

    def test_invalid_tenant_ids(self):
        """Test validation of invalid tenant IDs."""
        invalid_ids = [
            "",  # Empty
            None,  # None
            "tenant with spaces",  # Spaces
            "tenant@domain.com",  # Special chars
            "tenant/path",  # Slashes
            "tenant:key",  # Colons
            "a" * 300,  # Too long
        ]
        
        for tenant_id in invalid_ids:
            assert not validate_tenant_id(tenant_id), f"Should be invalid: {tenant_id}"

    def test_tenant_id_type_checking(self):
        """Test type checking for tenant ID validation."""
        assert not validate_tenant_id(123)  # Number
        assert not validate_tenant_id(["tenant"])  # List
        assert not validate_tenant_id({"id": "tenant"})  # Dict


class TestSanitizeChunkId:
    """Tests for sanitize_chunk_id function."""

    def test_basic_sanitization(self):
        """Test basic chunk ID sanitization."""
        result = sanitize_chunk_id("chunk-0")
        assert result == "chunk-0"

    def test_problematic_characters(self):
        """Test sanitization of problematic characters."""
        # Test colon replacement
        assert sanitize_chunk_id("chunk:0") == "chunk-0"
        
        # Test slash replacement
        assert sanitize_chunk_id("chunk/0") == "chunk-0"
        
        # Test space replacement
        assert sanitize_chunk_id("chunk 0") == "chunk_0"
        
        # Test multiple replacements
        assert sanitize_chunk_id("chunk: part/0 test") == "chunk-_part-0_test"

    def test_empty_chunk_id(self):
        """Test handling of empty chunk ID."""
        assert sanitize_chunk_id("") == "unknown"
        assert sanitize_chunk_id(None) == "unknown"

    def test_length_limiting(self):
        """Test that long chunk IDs are truncated."""
        long_id = "a" * 150  # Longer than 100 char limit
        result = sanitize_chunk_id(long_id)
        
        assert len(result) == 100
        assert result == "a" * 100

    def test_sanitization_stability(self):
        """Test that sanitization is stable across calls."""
        problematic_id = "chunk: test/part 0"
        
        results = [sanitize_chunk_id(problematic_id) for _ in range(3)]
        
        assert len(set(results)) == 1
        assert all(r == results[0] for r in results)
