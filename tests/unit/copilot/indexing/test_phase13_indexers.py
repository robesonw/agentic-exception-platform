"""
Tests for Phase 13 Copilot Intelligence Indexers.

Tests both AuditEventsIndexer and ToolRegistryIndexer with focus on:
- Tenant isolation and scoping
- Sensitive data redaction for tools
- Incremental indexing with watermarks  
- Security compliance (no secrets in indexed content)

Cross-reference:
- docs/phase13-copilot-intelligence-mvp.md
- tasks: P13-7 (AuditEventsIndexer), P13-8 (ToolRegistryIndexer)
"""

import json
import pytest
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import MagicMock, AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    GovernanceAuditEvent,
    ToolDefinition,
    IndexingState,
    CopilotDocumentSourceType,
    Tenant,
)
from src.services.copilot.indexing.audit_events_indexer import (
    AuditEventsIndexer,
    AuditEventDoc,
)
from src.services.copilot.indexing.tool_registry_indexer import (
    ToolRegistryIndexer,
    ToolRegistryDoc,
    SENSITIVE_FIELD_PATTERNS,
    SENSITIVE_VALUE_PATTERNS,
)
from src.services.copilot.chunking_service import DocumentChunkingService, SourceDocument
from src.services.copilot.embedding_service import EmbeddingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository


class TestAuditEventsIndexer:
    """Test AuditEventsIndexer for tenant isolation and incremental processing."""

    @pytest.fixture
    async def mock_dependencies(self):
        """Mock dependencies for testing."""
        db_session = MagicMock(spec=AsyncSession)
        embedding_service = MagicMock(spec=EmbeddingService)
        chunking_service = MagicMock(spec=DocumentChunkingService)
        document_repository = MagicMock(spec=CopilotDocumentRepository)
        
        # Mock chunking service to return test chunks
        chunking_service.chunk_document = MagicMock(return_value=[
            {"content": "Test chunk", "metadata": {}}
        ])
        
        # Mock document repository for batch operations
        document_repository.upsert_documents_batch = AsyncMock(return_value=1)
        
        return {
            "db_session": db_session,
            "embedding_service": embedding_service,
            "chunking_service": chunking_service,
            "document_repository": document_repository,
        }

    @pytest.fixture
    def sample_audit_events(self):
        """Sample audit events for testing."""
        base_time = datetime.now(timezone.utc)
        
        return [
            GovernanceAuditEvent(
                id="audit-1",  # Changed from audit_event_id to id
                event_type="TOOL_ENABLED",
                entity_type="ToolDefinition",
                entity_id="tool-123",
                action="CREATE",
                actor_id="user-456",
                actor_role="Admin",
                tenant_id="tenant-1",  # Tenant-specific event
                diff_summary="Enabled webhook tool for finance domain",
                correlation_id="correlation-1",
                created_at=base_time,
                metadata={"domain": "finance"},
            ),
            GovernanceAuditEvent(
                id="audit-2",  # Changed from audit_event_id to id
                event_type="PACK_ACTIVATED",
                entity_type="DomainPack",
                entity_id="pack-789",
                action="UPDATE",
                actor_id="system",
                actor_role="System",
                tenant_id=None,  # Global admin event
                diff_summary="Activated healthcare domain pack globally",
                correlation_id="correlation-2", 
                created_at=base_time + timedelta(minutes=1),
                metadata={"domain": "healthcare"},
            ),
            GovernanceAuditEvent(
                id="audit-3",  # Changed from audit_event_id to id
                event_type="POLICY_VIOLATION",
                entity_type="Exception",
                entity_id="exc-999",
                action="ALERT",
                actor_id="user-789",
                actor_role="TenantAdmin", 
                tenant_id="tenant-2",  # Different tenant
                diff_summary="Rate limit exceeded for API endpoint",
                correlation_id="correlation-3",
                created_at=base_time + timedelta(minutes=2),
                metadata={"endpoint": "/api/process", "rate_limit": 100},
            ),
        ]

    @pytest.mark.asyncio
    async def test_audit_events_tenant_isolation(self, mock_dependencies, sample_audit_events):
        """Test that audit events are properly isolated by tenant."""
        indexer = AuditEventsIndexer(**mock_dependencies)
        
        # Mock database query to return filtered events
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_audit_events[0]]  # Only tenant-1 event
        mock_dependencies["db_session"].execute = AsyncMock(return_value=mock_result)
        
        # Mock watermark retrieval
        with patch.object(indexer, '_get_watermark', return_value=None):
            with patch.object(indexer, '_update_watermark', return_value=None):
                result = await indexer.index_audit_events_incremental(tenant_id="tenant-1")
        
        # Verify tenant isolation in query
        call_args = mock_dependencies["db_session"].execute.call_args[0][0]
        assert "tenant_id = :tenant_id_1" in str(call_args) or "tenant_id == :param_1" in str(call_args)
        
        # Verify successful processing
        assert result.success
        assert result.tenant_id == "tenant-1"
        assert result.chunks_processed >= 0

    @pytest.mark.asyncio
    async def test_audit_events_global_handling(self, mock_dependencies, sample_audit_events):
        """Test that global audit events (tenant_id=NULL) are handled correctly."""
        indexer = AuditEventsIndexer(**mock_dependencies)
        
        # Mock database query to return global event
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_audit_events[1]]  # Global event
        mock_dependencies["db_session"].execute = AsyncMock(return_value=mock_result)
        
        # Mock watermark operations for global events
        with patch.object(indexer, '_get_watermark', return_value=None) as mock_get_watermark:
            with patch.object(indexer, '_update_watermark', return_value=None) as mock_update_watermark:
                result = await indexer.index_audit_events_incremental(tenant_id=None)
        
        # Verify global watermark handling (uses 'GLOBAL' as tenant key)
        mock_get_watermark.assert_called_with('GLOBAL')
        mock_update_watermark.assert_called()
        
        # Verify successful processing
        assert result.success
        assert result.tenant_id is None

    @pytest.mark.asyncio  
    async def test_audit_events_incremental_watermark(self, mock_dependencies, sample_audit_events):
        """Test incremental indexing with created_at watermarks."""
        indexer = AuditEventsIndexer(**mock_dependencies)
        
        # Mock existing watermark (should filter out older events)
        existing_watermark = sample_audit_events[0].created_at
        
        # Mock database to return only newer events
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_audit_events[2]]  # Only newer event
        mock_dependencies["db_session"].execute = AsyncMock(return_value=mock_result)
        
        with patch.object(indexer, '_get_watermark', return_value=existing_watermark):
            with patch.object(indexer, '_update_watermark', return_value=None) as mock_update:
                result = await indexer.index_audit_events_incremental(tenant_id="tenant-2")
        
        # Verify watermark was updated with latest event time
        mock_update.assert_called()
        
        # Verify query included watermark filter
        call_args = mock_dependencies["db_session"].execute.call_args[0][0]
        assert "created_at >" in str(call_args)
        
        assert result.success

    def test_audit_event_doc_to_source_document(self, sample_audit_events):
        """Test conversion of audit event to indexable source document."""
        audit_event = sample_audit_events[0]
        
        doc = AuditEventDoc(
            event_id=audit_event.id,  # Changed from audit_event_id to id
            tenant_id=audit_event.tenant_id,
            event_type=audit_event.event_type,
            entity_type=audit_event.entity_type,
            entity_id=audit_event.entity_id,
            action=audit_event.action,
            actor_id=audit_event.actor_id,
            actor_role=audit_event.actor_role,
            diff_summary=audit_event.diff_summary,
            created_at=audit_event.created_at,
            correlation_id=audit_event.correlation_id,
            metadata=audit_event.metadata,
        )
        
        source_doc = doc.to_source_document()
        
        # Verify document structure
        assert source_doc.source_type == CopilotDocumentSourceType.AUDIT_EVENT
        assert source_doc.source_id == audit_event.id  # Changed from audit_event_id to id
        assert source_doc.tenant_id == audit_event.tenant_id
        
        # Verify content includes key audit information
        assert audit_event.event_type in source_doc.content
        assert audit_event.action in source_doc.content
        assert audit_event.diff_summary in source_doc.content
        assert audit_event.actor_role in source_doc.content
        
        # Verify metadata
        assert source_doc.metadata["event_type"] == audit_event.event_type
        assert source_doc.metadata["entity_type"] == audit_event.entity_type
        assert source_doc.metadata["actor_role"] == audit_event.actor_role


class TestToolRegistryIndexer:
    """Test ToolRegistryIndexer for sensitive data redaction and tenant isolation."""

    @pytest.fixture
    async def mock_dependencies(self):
        """Mock dependencies for testing."""
        db_session = MagicMock(spec=AsyncSession)
        embedding_service = MagicMock(spec=EmbeddingService)
        chunking_service = MagicMock(spec=DocumentChunkingService)
        document_repository = MagicMock(spec=CopilotDocumentRepository)
        
        # Mock chunking service
        chunking_service.chunk_document = MagicMock(return_value=[
            {"content": "Test chunk", "metadata": {}}
        ])
        
        # Mock document repository
        document_repository.upsert_documents_batch = AsyncMock(return_value=1)
        
        return {
            "db_session": db_session,
            "embedding_service": embedding_service,
            "chunking_service": chunking_service,
            "document_repository": document_repository,
        }

    @pytest.fixture
    def sample_tools(self):
        """Sample tool definitions for testing (including sensitive data)."""
        return [
            ToolDefinition(
                tool_id="tool-1",
                tenant_id="tenant-1",
                name="WebhookTool",
                type="webhook",
                config={
                    "description": "Send HTTP webhooks to external systems",
                    "capabilities": ["POST", "GET", "PUT"],
                    "base_url": "https://api.example.com",
                    "auth": {
                        "type": "bearer",
                        "token": "sk-1234567890abcdef1234567890abcdef",  # SENSITIVE
                        "api_key": "ak-abcdef1234567890abcdef1234567890",   # SENSITIVE
                    },
                    "headers": {
                        "Authorization": "Bearer sk-token-here",           # SENSITIVE
                        "Content-Type": "application/json",               # SAFE
                    },
                    "connection_string": "postgres://user:pass@db/name",  # SENSITIVE
                    "timeout": 30,                                        # SAFE
                    "retries": 3,                                        # SAFE
                },
                created_at=datetime.now(timezone.utc),
            ),
            ToolDefinition(
                tool_id="tool-2",
                tenant_id="tenant-2",
                name="DatabaseTool", 
                type="database",
                config={
                    "description": "Query database for analytics",
                    "supported_operations": ["SELECT", "AGGREGATE"],
                    "database_url": "postgresql://secret:password@host/db",  # SENSITIVE
                    "query_timeout": 60,                                     # SAFE
                    "max_rows": 1000,                                       # SAFE
                    "credentials": {                                        # SENSITIVE SECTION
                        "username": "dbuser",
                        "password": "super_secret_password_123",
                        "secret_key": "abcd1234567890efgh",
                    },
                },
                created_at=datetime.now(timezone.utc),
            ),
            ToolDefinition(
                tool_id="tool-3",
                tenant_id=None,  # Global tool
                name="LoggingTool",
                type="logging",
                config={
                    "description": "Centralized logging and monitoring",
                    "capabilities": ["log", "alert", "monitor"],
                    "log_level": "INFO",                                    # SAFE
                    "endpoints": ["syslog", "webhook", "file"],            # SAFE
                    "api_credentials": {                                    # SENSITIVE SECTION
                        "client_id": "client_123",
                        "client_secret": "cs_1234567890abcdefghijklmnop",
                        "oauth_token": "oauth2_abcdef1234567890",
                    },
                },
                created_at=datetime.now(timezone.utc),
            ),
        ]

    @pytest.mark.asyncio
    async def test_tool_registry_tenant_isolation(self, mock_dependencies, sample_tools):
        """Test that tools are properly isolated by tenant."""
        indexer = ToolRegistryIndexer(**mock_dependencies)
        
        # Mock database query to return only tenant-1 tools
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_tools[0]]  # Only tenant-1 tool
        mock_dependencies["db_session"].execute = AsyncMock(return_value=mock_result)
        
        result = await indexer.index_tools_for_tenant(tenant_id="tenant-1")
        
        # Verify tenant filtering in query
        call_args = mock_dependencies["db_session"].execute.call_args[0][0]
        assert "tenant_id = :tenant_id_1" in str(call_args) or "tenant_id == :param_1" in str(call_args)
        
        assert result.success
        assert result.tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_tool_registry_global_tools(self, mock_dependencies, sample_tools):
        """Test indexing global tools (tenant_id=NULL)."""
        indexer = ToolRegistryIndexer(**mock_dependencies)
        
        # Mock database query to return global tool
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_tools[2]]  # Global tool
        mock_dependencies["db_session"].execute = AsyncMock(return_value=mock_result)
        
        result = await indexer.index_tools_for_tenant(tenant_id=None)
        
        # Verify query for global tools (tenant_id IS NULL)
        call_args = mock_dependencies["db_session"].execute.call_args[0][0] 
        assert "tenant_id IS NULL" in str(call_args) or "tenant_id.is_(None)" in str(call_args)
        
        assert result.success
        assert result.tenant_id is None

    def test_sensitive_config_redaction(self, sample_tools):
        """Test that sensitive configuration data is properly redacted."""
        indexer = ToolRegistryIndexer(
            db_session=MagicMock(),
            embedding_service=MagicMock(),
            chunking_service=MagicMock(),
            document_repository=MagicMock(),
        )
        
        # Test redaction on webhook tool (lots of sensitive data)
        webhook_tool = sample_tools[0]
        redacted_config = indexer._redact_sensitive_config(webhook_tool.config)
        
        # Verify sensitive data is removed
        assert "auth" not in redacted_config  # Entire auth section should be gone
        assert "headers" in redacted_config   # Headers section should exist
        assert "Authorization" not in redacted_config["headers"]  # But sensitive header removed
        assert "Content-Type" in redacted_config["headers"]      # Safe header preserved
        assert "connection_string" not in redacted_config        # Connection string removed
        
        # Verify safe data is preserved
        assert redacted_config["description"] == webhook_tool.config["description"]
        assert redacted_config["capabilities"] == webhook_tool.config["capabilities"]
        assert redacted_config["base_url"] == webhook_tool.config["base_url"]
        assert redacted_config["timeout"] == webhook_tool.config["timeout"]
        assert redacted_config["retries"] == webhook_tool.config["retries"]
        
        # Test redaction on database tool
        db_tool = sample_tools[1]
        redacted_db_config = indexer._redact_sensitive_config(db_tool.config)
        
        # Verify sensitive data removed
        assert "database_url" not in redacted_db_config
        assert "credentials" not in redacted_db_config
        
        # Verify safe data preserved
        assert redacted_db_config["description"] == db_tool.config["description"]
        assert redacted_db_config["supported_operations"] == db_tool.config["supported_operations"]
        assert redacted_db_config["query_timeout"] == db_tool.config["query_timeout"]
        assert redacted_db_config["max_rows"] == db_tool.config["max_rows"]

    def test_sensitive_field_detection(self):
        """Test detection of sensitive field names."""
        indexer = ToolRegistryIndexer(
            db_session=MagicMock(),
            embedding_service=MagicMock(),
            chunking_service=MagicMock(),
            document_repository=MagicMock(),
        )
        
        # Test obvious sensitive fields
        assert indexer._is_sensitive_field("password")
        assert indexer._is_sensitive_field("api_key")
        assert indexer._is_sensitive_field("secret")
        assert indexer._is_sensitive_field("token")
        assert indexer._is_sensitive_field("authorization")
        assert indexer._is_sensitive_field("connection_string")
        assert indexer._is_sensitive_field("oauth_token")
        
        # Test pattern matches
        assert indexer._is_sensitive_field("client_secret")  # Contains "secret"
        assert indexer._is_sensitive_field("auth_token")     # Contains "token"
        assert indexer._is_sensitive_field("db_password")    # Contains "password"
        assert indexer._is_sensitive_field("private_key")    # Ends with "_key"
        
        # Test safe fields
        assert not indexer._is_sensitive_field("description")
        assert not indexer._is_sensitive_field("timeout")
        assert not indexer._is_sensitive_field("base_url")
        assert not indexer._is_sensitive_field("capabilities")
        assert not indexer._is_sensitive_field("content_type")  # Not "content-type"

    def test_sensitive_value_detection(self):
        """Test detection of sensitive values by pattern."""
        indexer = ToolRegistryIndexer(
            db_session=MagicMock(),
            embedding_service=MagicMock(),
            chunking_service=MagicMock(),
            document_repository=MagicMock(),
        )
        
        # Test token-like values
        assert indexer._is_sensitive_value("sk-1234567890abcdef1234567890abcdef")  # Starts with sk-
        assert indexer._is_sensitive_value("pk-abcdefghijklmnopqrstuvwxyz123456")  # Starts with pk-
        assert indexer._is_sensitive_value("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")  # Bearer token
        
        # Test base64-like strings
        assert indexer._is_sensitive_value("YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY3ODkw")  # Long base64
        
        # Test connection strings
        assert indexer._is_sensitive_value("postgres://user:pass@host/db")
        assert indexer._is_sensitive_value("mysql://root:secret@localhost/mydb")
        assert indexer._is_sensitive_value("https://user:pass@api.example.com/data")
        
        # Test hex strings (potential keys)
        assert indexer._is_sensitive_value("a1b2c3d4e5f6789012345678901234567890abcdef123456")  # Long hex
        
        # Test safe values
        assert not indexer._is_sensitive_value("description")      # Too short and safe
        assert not indexer._is_sensitive_value("https://api.example.com")  # URL without auth
        assert not indexer._is_sensitive_value("POST")             # HTTP method
        assert not indexer._is_sensitive_value("application/json") # Content type
        assert not indexer._is_sensitive_value("30")               # Number as string

    def test_capabilities_extraction(self, sample_tools):
        """Test extraction of tool capabilities from config."""
        indexer = ToolRegistryIndexer(
            db_session=MagicMock(),
            embedding_service=MagicMock(),
            chunking_service=MagicMock(),
            document_repository=MagicMock(),
        )
        
        # Test webhook tool capabilities
        webhook_capabilities = indexer._extract_capabilities(sample_tools[0].config)
        expected_webhook_caps = {"POST", "GET", "PUT"}
        assert set(webhook_capabilities) == expected_webhook_caps
        
        # Test database tool capabilities
        db_capabilities = indexer._extract_capabilities(sample_tools[1].config)
        expected_db_caps = {"SELECT", "AGGREGATE"}
        assert set(db_capabilities) == expected_db_caps
        
        # Test logging tool capabilities
        logging_capabilities = indexer._extract_capabilities(sample_tools[2].config)
        expected_logging_caps = {"log", "alert", "monitor"}
        assert set(logging_capabilities) == expected_logging_caps

    def test_tool_registry_doc_content_safety(self, sample_tools):
        """Test that ToolRegistryDoc content contains no sensitive data."""
        indexer = ToolRegistryIndexer(
            db_session=MagicMock(),
            embedding_service=MagicMock(),
            chunking_service=MagicMock(),
            document_repository=MagicMock(),
        )
        
        # Convert tool with sensitive data
        webhook_tool = sample_tools[0]
        tool_doc = indexer._convert_tool_to_doc(webhook_tool)
        source_doc = tool_doc.to_source_document()
        
        content = source_doc.content.lower()
        
        # Verify NO sensitive data in content
        assert "sk-1234567890abcdef1234567890abcdef" not in content
        assert "ak-abcdef1234567890abcdef1234567890" not in content
        assert "bearer sk-token-here" not in content
        assert "postgres://user:pass@db/name" not in content
        assert "authorization" not in content
        
        # Verify safe data IS in content
        assert "webhooktool" in content
        assert "webhook" in content
        assert "send http webhooks to external systems" in content
        assert "post" in content
        assert "get" in content
        assert "put" in content
        assert "https://api.example.com" in content
        assert "30" in content  # timeout
        assert "3" in content   # retries
        assert "application/json" in content  # safe header

    @pytest.mark.asyncio
    async def test_indexed_content_has_no_secrets(self, mock_dependencies, sample_tools):
        """Integration test: verify no secrets appear in final indexed content."""
        indexer = ToolRegistryIndexer(**mock_dependencies)
        
        # Mock database query 
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_tools
        mock_dependencies["db_session"].execute = AsyncMock(return_value=mock_result)
        
        # Capture chunks sent to document repository
        indexed_chunks = []
        async def capture_chunks(tenant_id, chunks):
            indexed_chunks.extend(chunks)
            return len(chunks)
        
        mock_dependencies["document_repository"].upsert_documents_batch = capture_chunks
        
        # Index the tools
        result = await indexer.index_tools_for_tenant(tenant_id="tenant-1")
        
        # Verify no sensitive patterns in any indexed chunk
        sensitive_patterns = [
            r"sk-[a-z0-9]{32,}",                    # Secret keys
            r"ak-[a-z0-9]{32,}",                    # API keys
            r"bearer\s+[a-z0-9]{16,}",              # Bearer tokens
            r"postgres://.*:.*@",                    # Connection strings with auth
            r"password.*:",                          # Password fields
            r"secret.*:",                           # Secret fields
            r"token.*:",                            # Token fields
        ]
        
        for chunk in indexed_chunks:
            content = chunk.get("content", "").lower()
            for pattern in sensitive_patterns:
                matches = re.search(pattern, content)
                assert matches is None, f"Found sensitive data in chunk: {matches.group()}"
        
        assert result.success