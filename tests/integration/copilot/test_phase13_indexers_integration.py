"""
Integration tests for Phase 13 Copilot Intelligence Indexers.

Tests end-to-end functionality with real database operations:
- Audit events indexing with tenant isolation
- Tool registry indexing with sensitive data redaction
- Watermark-based incremental processing
- Security compliance verification

Cross-reference:
- docs/phase13-copilot-intelligence-mvp.md
- tasks: P13-7 (AuditEventsIndexer), P13-8 (ToolRegistryIndexer)
"""

import json
import pytest
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    GovernanceAuditEvent,
    ToolDefinition,
    IndexingState,
    CopilotDocumentSourceType,
    CopilotDocument,
    Tenant,
)
from src.services.copilot.indexing.audit_events_indexer import AuditEventsIndexer
from src.services.copilot.indexing.tool_registry_indexer import ToolRegistryIndexer
from src.services.copilot.chunking_service import DocumentChunkingService
from src.services.copilot.embedding_service import EmbeddingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from tests.conftest import test_db_session  # Assuming this exists for DB testing


@pytest.mark.asyncio
@pytest.mark.integration
class TestPhase13IndexersIntegration:
    """Integration tests for Phase 13 audit events and tool registry indexers."""

    @pytest.fixture
    async def db_session(self):
        """Get database session for testing."""
        # This should provide a real test database session
        # Implementation depends on your test database setup
        async with test_db_session() as session:
            yield session

    @pytest.fixture
    async def test_tenants(self, db_session: AsyncSession):
        """Create test tenants for isolation testing."""
        tenant1 = Tenant(
            tenant_id="test-tenant-1",
            name="Test Tenant 1",
            status="active",
            created_at=datetime.now(timezone.utc),
        )
        tenant2 = Tenant(
            tenant_id="test-tenant-2",
            name="Test Tenant 2", 
            status="active",
            created_at=datetime.now(timezone.utc),
        )
        
        db_session.add_all([tenant1, tenant2])
        await db_session.commit()
        
        yield [tenant1, tenant2]
        
        # Cleanup
        await db_session.execute(delete(Tenant).where(Tenant.tenant_id.in_(["test-tenant-1", "test-tenant-2"])))
        await db_session.commit()

    @pytest.fixture
    async def test_audit_events(self, db_session: AsyncSession, test_tenants: List[Tenant]):
        """Create test audit events for different tenants and global events."""
        base_time = datetime.now(timezone.utc)
        
        events = [
            # Tenant 1 events
            GovernanceAuditEvent(
                audit_event_id=str(uuid4()),
                event_type="TOOL_ENABLED",
                entity_type="ToolDefinition",
                entity_id="tool-123",
                action="CREATE",
                actor_id="user-456",
                actor_role="Admin",
                tenant_id="test-tenant-1",
                diff_summary="Enabled webhook tool for finance domain",
                correlation_id=str(uuid4()),
                created_at=base_time,
                metadata={"domain": "finance", "tool_name": "WebhookTool"},
            ),
            GovernanceAuditEvent(
                audit_event_id=str(uuid4()),
                event_type="POLICY_UPDATED",
                entity_type="TenantPolicy",
                entity_id="policy-456",
                action="UPDATE",
                actor_id="user-789",
                actor_role="TenantAdmin",
                tenant_id="test-tenant-1",
                diff_summary="Updated rate limiting policy to 1000 req/min",
                correlation_id=str(uuid4()),
                created_at=base_time + timedelta(minutes=1),
                metadata={"policy_type": "rate_limit", "new_value": 1000},
            ),
            # Tenant 2 events
            GovernanceAuditEvent(
                audit_event_id=str(uuid4()),
                event_type="PACK_ACTIVATED",
                entity_type="DomainPack",
                entity_id="pack-789",
                action="ACTIVATE",
                actor_id="user-123",
                actor_role="Admin",
                tenant_id="test-tenant-2",
                diff_summary="Activated healthcare domain pack",
                correlation_id=str(uuid4()),
                created_at=base_time + timedelta(minutes=2),
                metadata={"domain": "healthcare", "pack_version": "1.2.0"},
            ),
            # Global admin events (tenant_id=NULL)
            GovernanceAuditEvent(
                audit_event_id=str(uuid4()),
                event_type="SYSTEM_MAINTENANCE",
                entity_type="System",
                entity_id="system",
                action="MAINTENANCE",
                actor_id="system",
                actor_role="System",
                tenant_id=None,  # Global event
                diff_summary="Performed system maintenance and updates",
                correlation_id=str(uuid4()),
                created_at=base_time + timedelta(minutes=3),
                metadata={"maintenance_type": "security_updates", "downtime": "0"},
            ),
            GovernanceAuditEvent(
                audit_event_id=str(uuid4()),
                event_type="PLATFORM_UPDATE",
                entity_type="Platform",
                entity_id="platform",
                action="UPDATE",
                actor_id="admin",
                actor_role="PlatformAdmin",
                tenant_id=None,  # Global event
                diff_summary="Updated platform to version 2.1.0",
                correlation_id=str(uuid4()),
                created_at=base_time + timedelta(minutes=4),
                metadata={"version": "2.1.0", "features": ["copilot", "rag"]},
            ),
        ]
        
        db_session.add_all(events)
        await db_session.commit()
        
        yield events
        
        # Cleanup
        event_ids = [event.audit_event_id for event in events]
        await db_session.execute(delete(GovernanceAuditEvent).where(GovernanceAuditEvent.audit_event_id.in_(event_ids)))
        await db_session.commit()

    @pytest.fixture  
    async def test_tools(self, db_session: AsyncSession, test_tenants: List[Tenant]):
        """Create test tool definitions with sensitive configuration data."""
        tools = [
            # Tenant 1 tool with sensitive config
            ToolDefinition(
                tool_id=str(uuid4()),
                tenant_id="test-tenant-1",
                name="WebhookIntegration",
                type="webhook",
                config={
                    "description": "Send webhooks to external payment systems",
                    "capabilities": ["POST", "GET", "PUT", "DELETE"],
                    "base_url": "https://api.payments.com",
                    "timeout": 30,
                    "retries": 3,
                    # Sensitive data that should be redacted
                    "auth": {
                        "type": "bearer",
                        "token": "sk-live_1234567890abcdef1234567890abcdef",
                        "api_key": "ak_live_abcdefghijklmnopqrstuvwxyz123456",
                    },
                    "headers": {
                        "Authorization": "Bearer sk-secret-token-here", 
                        "Content-Type": "application/json",
                        "X-API-Version": "2023-01",
                    },
                    "connection_string": "postgres://dbuser:supersecret@db.payments.com/payments",
                    "oauth_config": {
                        "client_id": "client_12345",
                        "client_secret": "cs_abcdefghijklmnopqrstuvwxyz123456789",
                        "oauth_token": "oauth2_zyxwvutsrqponmlkjihgfedcba987654",
                    },
                },
                created_at=datetime.now(timezone.utc),
            ),
            # Tenant 2 tool with different sensitive config
            ToolDefinition(
                tool_id=str(uuid4()),
                tenant_id="test-tenant-2",
                name="DatabaseAnalytics",
                type="database",
                config={
                    "description": "Advanced analytics queries on patient data",
                    "supported_operations": ["SELECT", "AGGREGATE", "ANALYZE"],
                    "query_timeout": 120,
                    "max_rows": 10000,
                    "read_only": True,
                    # Sensitive data
                    "database_url": "postgresql://analytics_user:medical_secret_789@analytics.hospital.com/patient_db",
                    "credentials": {
                        "username": "analytics_user",
                        "password": "medical_secret_789",
                        "secret_key": "sk_analytics_abcdef1234567890ghijklmnop",
                        "private_key_file": "/secrets/analytics_private_key.pem",
                    },
                    "ssl_config": {
                        "ssl_cert": "/certs/client.crt",
                        "ssl_key": "/certs/client.key",
                        "ssl_ca": "/certs/ca.crt",
                    },
                },
                created_at=datetime.now(timezone.utc) + timedelta(minutes=1),
            ),
            # Global tool with minimal sensitive data
            ToolDefinition(
                tool_id=str(uuid4()),
                tenant_id=None,  # Global tool
                name="SystemLogger",
                type="logging",
                config={
                    "description": "Centralized logging for platform events",
                    "capabilities": ["log", "alert", "monitor", "archive"],
                    "log_levels": ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
                    "max_log_size": "100MB",
                    "retention_days": 90,
                    # Some sensitive config
                    "api_credentials": {
                        "service_account_key": "sa_1234567890abcdefghijklmnopqrstuvwxyz",
                        "oauth_token": "logging_oauth_abcdef1234567890",
                    },
                    "syslog_config": {
                        "host": "logs.platform.com",
                        "port": 514,
                        "protocol": "tcp",
                        "auth_token": "syslog_token_1234567890abcdef",
                    },
                },
                created_at=datetime.now(timezone.utc) + timedelta(minutes=2),
            ),
        ]
        
        db_session.add_all(tools)
        await db_session.commit()
        
        yield tools
        
        # Cleanup
        tool_ids = [tool.tool_id for tool in tools]
        await db_session.execute(delete(ToolDefinition).where(ToolDefinition.tool_id.in_(tool_ids)))
        await db_session.commit()

    @pytest.fixture
    async def indexer_services(self, db_session: AsyncSession):
        """Create real indexer services for testing."""
        # Create mock services (or real ones if available)
        # These would typically be injected from your DI container
        embedding_service = MockEmbeddingService()
        chunking_service = DocumentChunkingService()
        document_repository = CopilotDocumentRepository(db_session)
        
        return {
            "embedding_service": embedding_service,
            "chunking_service": chunking_service,
            "document_repository": document_repository,
        }

    @pytest.mark.asyncio
    async def test_audit_events_tenant_isolation_integration(
        self, 
        db_session: AsyncSession, 
        test_audit_events: List[GovernanceAuditEvent],
        indexer_services: Dict[str, Any]
    ):
        """Test that audit events indexing properly isolates tenants."""
        # Create audit events indexer
        indexer = AuditEventsIndexer(
            db_session=db_session,
            **indexer_services
        )
        
        # Index events for tenant 1
        result1 = await indexer.index_audit_events_incremental(tenant_id="test-tenant-1")
        assert result1.success
        assert result1.tenant_id == "test-tenant-1"
        assert result1.chunks_processed >= 2  # Should have 2 events for tenant-1
        
        # Index events for tenant 2  
        result2 = await indexer.index_audit_events_incremental(tenant_id="test-tenant-2")
        assert result2.success
        assert result2.tenant_id == "test-tenant-2"
        assert result2.chunks_processed >= 1  # Should have 1 event for tenant-2
        
        # Index global events
        result_global = await indexer.index_audit_events_incremental(tenant_id=None)
        assert result_global.success
        assert result_global.tenant_id is None
        assert result_global.chunks_processed >= 2  # Should have 2 global events
        
        # Verify tenant isolation in stored documents
        tenant1_docs = await self._get_copilot_documents(db_session, "test-tenant-1", CopilotDocumentSourceType.AUDIT_EVENT)
        tenant2_docs = await self._get_copilot_documents(db_session, "test-tenant-2", CopilotDocumentSourceType.AUDIT_EVENT)
        global_docs = await self._get_copilot_documents(db_session, None, CopilotDocumentSourceType.AUDIT_EVENT)
        
        # Each tenant should only see their own events
        assert len(tenant1_docs) >= 2
        assert len(tenant2_docs) >= 1
        assert len(global_docs) >= 2
        
        # Verify content isolation
        for doc in tenant1_docs:
            assert "test-tenant-1" in str(doc.metadata) or "finance" in doc.content.lower()
        
        for doc in tenant2_docs:
            assert "test-tenant-2" in str(doc.metadata) or "healthcare" in doc.content.lower()

    @pytest.mark.asyncio
    async def test_tool_registry_sensitive_data_redaction_integration(
        self,
        db_session: AsyncSession,
        test_tools: List[ToolDefinition],
        indexer_services: Dict[str, Any]
    ):
        """Test that tool registry indexing properly redacts sensitive data."""
        # Create tool registry indexer
        indexer = ToolRegistryIndexer(
            db_session=db_session,
            **indexer_services
        )
        
        # Index tools for tenant 1
        result1 = await indexer.index_tools_for_tenant(tenant_id="test-tenant-1")
        assert result1.success
        assert result1.chunks_processed >= 1
        
        # Index tools for tenant 2
        result2 = await indexer.index_tools_for_tenant(tenant_id="test-tenant-2")
        assert result2.success
        assert result2.chunks_processed >= 1
        
        # Index global tools
        result_global = await indexer.index_tools_for_tenant(tenant_id=None)
        assert result_global.success
        assert result_global.chunks_processed >= 1
        
        # Get all indexed tool documents
        all_tool_docs = []
        all_tool_docs.extend(await self._get_copilot_documents(db_session, "test-tenant-1", CopilotDocumentSourceType.TOOL_REGISTRY))
        all_tool_docs.extend(await self._get_copilot_documents(db_session, "test-tenant-2", CopilotDocumentSourceType.TOOL_REGISTRY))
        all_tool_docs.extend(await self._get_copilot_documents(db_session, None, CopilotDocumentSourceType.TOOL_REGISTRY))
        
        assert len(all_tool_docs) >= 3  # Should have at least 3 tools indexed
        
        # Define sensitive patterns that should NOT appear in indexed content
        sensitive_patterns = [
            # Specific secrets from test data
            r"sk-live_1234567890abcdef1234567890abcdef",
            r"ak_live_abcdefghijklmnopqrstuvwxyz123456", 
            r"cs_abcdefghijklmnopqrstuvwxyz123456789",
            r"oauth2_zyxwvutsrqponmlkjihgfedcba987654",
            r"medical_secret_789",
            r"sk_analytics_abcdef1234567890ghijklmnop",
            r"sa_1234567890abcdefghijklmnopqrstuvwxyz",
            r"syslog_token_1234567890abcdef",
            
            # Connection strings with credentials
            r"postgres://.*:.*@",
            r"postgresql://.*:.*@",
            
            # General sensitive patterns  
            r"Bearer sk-",
            r"Authorization.*Bearer",
            r"password.*:",
            r"secret.*:",
            r"token.*:",
            r"oauth_token",
            r"client_secret",
            r"private_key",
        ]
        
        # Verify NO sensitive data in indexed content
        for doc in all_tool_docs:
            content_lower = doc.content.lower()
            metadata_str = json.dumps(doc.metadata or {}).lower()
            full_text = content_lower + " " + metadata_str
            
            for pattern in sensitive_patterns:
                matches = re.search(pattern, full_text, re.IGNORECASE)
                assert matches is None, f"Found sensitive data '{matches.group()}' in indexed document {doc.document_id}"
        
        # Verify safe data IS present
        safe_data_found = {
            "webhookintegration": False,
            "databaseanalytics": False,
            "systemlogger": False,
            "send webhooks to external payment systems": False,
            "advanced analytics queries": False,
            "centralized logging": False,
            "post": False,
            "select": False,
            "log": False,
        }
        
        for doc in all_tool_docs:
            content_lower = doc.content.lower()
            for safe_data in safe_data_found.keys():
                if safe_data in content_lower:
                    safe_data_found[safe_data] = True
        
        # Verify essential safe data was preserved
        assert safe_data_found["webhookintegration"] or safe_data_found["databaseanalytics"] or safe_data_found["systemlogger"]
        assert any(safe_data_found.values()), "No safe data found in indexed tools"

    @pytest.mark.asyncio
    async def test_watermark_incremental_processing_integration(
        self,
        db_session: AsyncSession,
        test_audit_events: List[GovernanceAuditEvent],
        indexer_services: Dict[str, Any]
    ):
        """Test watermark-based incremental processing."""
        indexer = AuditEventsIndexer(
            db_session=db_session,
            **indexer_services
        )
        
        # First indexing - should process all events
        result1 = await indexer.index_audit_events_incremental(tenant_id="test-tenant-1")
        assert result1.success
        initial_chunks = result1.chunks_processed
        assert initial_chunks >= 2  # Should find 2 events for tenant-1
        
        # Check watermark was created
        watermark_state = await db_session.get(IndexingState, ("test-tenant-1", CopilotDocumentSourceType.AUDIT_EVENT))
        assert watermark_state is not None
        assert watermark_state.last_updated is not None
        
        # Second indexing - should process no new events (no new events added)
        result2 = await indexer.index_audit_events_incremental(tenant_id="test-tenant-1")
        assert result2.success
        assert result2.chunks_processed == 0  # No new events
        
        # Add a new event after the watermark
        new_event = GovernanceAuditEvent(
            audit_event_id=str(uuid4()),
            event_type="NEW_TOOL_ADDED",
            entity_type="ToolDefinition",
            entity_id="tool-new",
            action="CREATE",
            actor_id="user-999",
            actor_role="Admin",
            tenant_id="test-tenant-1",
            diff_summary="Added new analytics tool",
            correlation_id=str(uuid4()),
            created_at=datetime.now(timezone.utc),  # Recent time
            metadata={"tool_type": "analytics"},
        )
        
        db_session.add(new_event)
        await db_session.commit()
        
        try:
            # Third indexing - should process only the new event
            result3 = await indexer.index_audit_events_incremental(tenant_id="test-tenant-1")
            assert result3.success
            assert result3.chunks_processed >= 1  # Should find the new event
            
            # Verify watermark was updated
            updated_watermark_state = await db_session.get(IndexingState, ("test-tenant-1", CopilotDocumentSourceType.AUDIT_EVENT))
            assert updated_watermark_state.last_updated > watermark_state.last_updated
            
        finally:
            # Cleanup new event
            await db_session.execute(delete(GovernanceAuditEvent).where(GovernanceAuditEvent.audit_event_id == new_event.audit_event_id))
            await db_session.commit()

    async def _get_copilot_documents(
        self,
        db_session: AsyncSession,
        tenant_id: Optional[str],
        source_type: CopilotDocumentSourceType
    ) -> List[CopilotDocument]:
        """Helper to get copilot documents for tenant and source type."""
        query = select(CopilotDocument).where(
            CopilotDocument.source_type == source_type
        )
        
        if tenant_id is not None:
            query = query.where(CopilotDocument.tenant_id == tenant_id)
        else:
            query = query.where(CopilotDocument.tenant_id.is_(None))
        
        result = await db_session.execute(query)
        return result.scalars().all()


class MockEmbeddingService:
    """Mock embedding service for testing."""
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate mock embeddings."""
        # Return dummy embeddings of consistent dimension
        embedding_dim = 384  # Common dimension
        return [[0.1] * embedding_dim for _ in texts]
    
    def get_embedding_dimension(self) -> int:
        """Return embedding dimension."""
        return 384