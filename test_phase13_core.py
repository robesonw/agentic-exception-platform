"""
Simple test script for Phase 13 Indexers core functionality.
Tests just the key components without full test infrastructure.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

from src.services.copilot.indexing.tool_registry_indexer import (
    ToolRegistryIndexer, 
    ToolRegistryDoc,
    SENSITIVE_FIELD_PATTERNS,
    SENSITIVE_VALUE_PATTERNS,
)
from src.services.copilot.indexing.audit_events_indexer import AuditEventDoc
from src.infrastructure.db.models import ToolDefinition, CopilotDocumentSourceType
from datetime import datetime, timezone
from unittest.mock import MagicMock


def test_tool_indexer_redaction():
    """Test that sensitive data is properly redacted."""
    print("Testing tool registry redaction...")
    
    # Create a mock indexer just for the redaction methods
    class MockToolIndexer:
        def _redact_sensitive_config(self, config):
            # Copy the redaction logic
            indexer = ToolRegistryIndexer(
                db_session=MagicMock(),
                embedding_service=MagicMock(),
                chunking_service=MagicMock(),
                document_repository=MagicMock(),
            )
            return indexer._redact_sensitive_config(config)
        
        def _is_sensitive_field(self, field_name):
            indexer = ToolRegistryIndexer(
                db_session=MagicMock(),
                embedding_service=MagicMock(),
                chunking_service=MagicMock(),
                document_repository=MagicMock(),
            )
            return indexer._is_sensitive_field(field_name)
            
        def _is_sensitive_value(self, value):
            indexer = ToolRegistryIndexer(
                db_session=MagicMock(),
                embedding_service=MagicMock(),
                chunking_service=MagicMock(),
                document_repository=MagicMock(),
            )
            return indexer._is_sensitive_value(value)
    
    mock_indexer = MockToolIndexer()
    
    # Test config with sensitive data
    test_config = {
        "description": "A webhook tool",  # SAFE
        "capabilities": ["POST", "GET"],   # SAFE
        "timeout": 30,                    # SAFE
        "auth": {                         # SENSITIVE SECTION
            "token": "sk-1234567890abcdef",
            "api_key": "ak-secret-key"
        },
        "headers": {
            "Authorization": "Bearer token",  # SENSITIVE
            "Content-Type": "application/json"  # SAFE
        },
        "connection_string": "postgres://user:pass@host/db"  # SENSITIVE
    }
    
    redacted = mock_indexer._redact_sensitive_config(test_config)
    
    print("Original config:", test_config)
    print("Redacted config:", redacted)
    
    # Verify sensitive data removed
    assert "auth" not in redacted, "Auth section should be removed"
    assert "connection_string" not in redacted, "Connection string should be removed"
    assert "headers" in redacted, "Headers section should exist"
    assert "Authorization" not in redacted["headers"], "Authorization header should be removed"
    assert redacted["headers"]["Content-Type"] == "application/json", "Safe header should remain"
    
    # Verify safe data preserved
    assert redacted["description"] == "A webhook tool"
    assert redacted["capabilities"] == ["POST", "GET"]
    assert redacted["timeout"] == 30
    
    print("✓ Configuration redaction working correctly")
    
    # Test sensitive field detection
    assert mock_indexer._is_sensitive_field("password"), "Should detect 'password' as sensitive"
    assert mock_indexer._is_sensitive_field("api_key"), "Should detect 'api_key' as sensitive"
    assert mock_indexer._is_sensitive_field("secret"), "Should detect 'secret' as sensitive"
    assert mock_indexer._is_sensitive_field("auth_token"), "Should detect 'auth_token' as sensitive"
    assert not mock_indexer._is_sensitive_field("description"), "Should not detect 'description' as sensitive"
    assert not mock_indexer._is_sensitive_field("timeout"), "Should not detect 'timeout' as sensitive"
    
    print("✓ Sensitive field detection working correctly")
    
    # Test sensitive value detection
    assert mock_indexer._is_sensitive_value("sk-1234567890abcdef1234567890abcdef"), "Should detect token-like value"
    assert mock_indexer._is_sensitive_value("postgres://user:pass@host/db"), "Should detect connection string"
    assert mock_indexer._is_sensitive_value("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"), "Should detect Bearer token"
    assert not mock_indexer._is_sensitive_value("description text"), "Should not detect safe text"
    assert not mock_indexer._is_sensitive_value("30"), "Should not detect number as sensitive"
    
    print("✓ Sensitive value detection working correctly")


def test_tool_registry_doc():
    """Test tool registry document creation."""
    print("Testing tool registry document...")
    
    tool_doc = ToolRegistryDoc(
        tool_id="123",
        tenant_id="tenant-1",
        name="WebhookTool",
        type="webhook",
        safe_config={"description": "A safe webhook tool", "timeout": 30},
        capabilities=["POST", "GET"],
        description="Send webhooks to external systems",
        created_at=datetime.now(timezone.utc),
    )
    
    source_doc = tool_doc.to_source_document()
    
    # Verify document structure
    assert source_doc.source_type == CopilotDocumentSourceType.TOOL_REGISTRY
    assert source_doc.source_id == "123"
    assert "WebhookTool" in source_doc.content
    assert "webhook" in source_doc.content
    assert "POST" in source_doc.content
    assert "GET" in source_doc.content
    
    # Verify tenant_id is in metadata for later use
    assert source_doc.metadata["tool_name"] == "WebhookTool"
    
    print("✓ Tool registry document creation working correctly")


def test_audit_event_doc():
    """Test audit event document creation."""
    print("Testing audit event document...")
    
    audit_doc = AuditEventDoc(
        event_id="event-123",
        tenant_id="tenant-1",
        event_type="TOOL_ENABLED",
        entity_type="ToolDefinition",
        entity_id="tool-456",
        action="CREATE",
        actor_id="user-789",
        actor_role="Admin",
        diff_summary="Enabled webhook tool for finance",
        created_at=datetime.now(timezone.utc),
        correlation_id="corr-123",
        metadata={"domain": "finance"},
    )
    
    source_doc = audit_doc.to_source_document()
    
    # Verify document structure
    assert source_doc.source_type == CopilotDocumentSourceType.AUDIT_EVENT
    assert source_doc.source_id == "event-123"
    assert "TOOL_ENABLED" in source_doc.content
    assert "CREATE" in source_doc.content
    assert "Admin" in source_doc.content
    assert "Enabled webhook tool for finance" in source_doc.content
    
    # Verify metadata
    assert source_doc.metadata["event_type"] == "TOOL_ENABLED"
    
    print("✓ Audit event document creation working correctly")


if __name__ == "__main__":
    print("Running Phase 13 Indexers Core Tests...")
    print()
    
    try:
        test_tool_indexer_redaction()
        print()
        test_tool_registry_doc()
        print()
        test_audit_event_doc()
        print()
        print("🎉 All tests passed! Phase 13 indexers are working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)