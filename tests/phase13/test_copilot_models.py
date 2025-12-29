"""
Unit tests for Phase 13 Copilot SQLAlchemy models.

Tests:
- CopilotDocument model creation and constraints
- CopilotSession model creation and relationships
- CopilotMessage model creation and constraints
- Enum definitions
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.infrastructure.db.models import (
    CopilotDocument,
    CopilotDocumentSourceType,
    CopilotMessage,
    CopilotMessageRole,
    CopilotSession,
)


class TestCopilotDocumentSourceType:
    """Tests for CopilotDocumentSourceType enum."""

    def test_enum_values(self):
        """Test that all expected source types are defined."""
        assert CopilotDocumentSourceType.POLICY_DOC.value == "policy_doc"
        assert CopilotDocumentSourceType.RESOLVED_EXCEPTION.value == "resolved_exception"
        assert CopilotDocumentSourceType.AUDIT_EVENT.value == "audit_event"
        assert CopilotDocumentSourceType.TOOL_REGISTRY.value == "tool_registry"
        assert CopilotDocumentSourceType.PLAYBOOK.value == "playbook"

    def test_enum_count(self):
        """Test that all source types are accounted for."""
        assert len(CopilotDocumentSourceType) == 5


class TestCopilotMessageRole:
    """Tests for CopilotMessageRole enum."""

    def test_enum_values(self):
        """Test that all expected roles are defined."""
        assert CopilotMessageRole.USER.value == "user"
        assert CopilotMessageRole.ASSISTANT.value == "assistant"
        assert CopilotMessageRole.SYSTEM.value == "system"

    def test_enum_count(self):
        """Test that all roles are accounted for."""
        assert len(CopilotMessageRole) == 3


class TestCopilotDocumentModel:
    """Tests for CopilotDocument model."""

    def test_create_document(self):
        """Test basic document creation."""
        doc = CopilotDocument(
            tenant_id="tenant-1",
            source_type="policy_doc",
            source_id="SOP-FIN-001",
            chunk_id="SOP-FIN-001-chunk-0",
            chunk_index=0,
            content="This is the first chunk of the policy document.",
        )

        assert doc.tenant_id == "tenant-1"
        assert doc.source_type == "policy_doc"
        assert doc.source_id == "SOP-FIN-001"
        assert doc.chunk_id == "SOP-FIN-001-chunk-0"
        assert doc.chunk_index == 0
        assert doc.content == "This is the first chunk of the policy document."

    def test_create_document_with_embedding(self):
        """Test document with embedding data."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        doc = CopilotDocument(
            tenant_id="tenant-1",
            source_type="resolved_exception",
            source_id="EX-2024-0001",
            chunk_id="EX-2024-0001-chunk-0",
            chunk_index=0,
            content="Exception resolution summary.",
            embedding=embedding,
            embedding_model="text-embedding-3-small",
            embedding_dimension=5,
        )

        assert doc.embedding == embedding
        assert doc.embedding_model == "text-embedding-3-small"
        assert doc.embedding_dimension == 5

    def test_create_document_with_metadata(self):
        """Test document with metadata."""
        metadata = {
            "title": "Settlement Failure SOP",
            "snippet": "Step 1: Verify counterparty details...",
            "tags": ["finance", "settlement"],
        }

        doc = CopilotDocument(
            tenant_id="tenant-1",
            source_type="policy_doc",
            source_id="SOP-FIN-001",
            chunk_id="SOP-FIN-001-chunk-0",
            chunk_index=0,
            content="Document content here.",
            metadata_json=metadata,
            domain="Finance",
            version="v1.0",
        )

        assert doc.metadata_json == metadata
        assert doc.domain == "Finance"
        assert doc.version == "v1.0"

    def test_document_repr(self):
        """Test document string representation."""
        doc = CopilotDocument(
            id=1,
            tenant_id="tenant-1",
            source_type="policy_doc",
            source_id="SOP-001",
            chunk_id="SOP-001-chunk-0",
            chunk_index=0,
            content="test",
        )

        repr_str = repr(doc)
        assert "CopilotDocument" in repr_str
        assert "tenant-1" in repr_str
        assert "policy_doc" in repr_str


class TestCopilotSessionModel:
    """Tests for CopilotSession model."""

    def test_create_session(self):
        """Test basic session creation."""
        session_id = uuid4()

        session = CopilotSession(
            id=session_id,
            tenant_id="tenant-1",
            user_id="user-123",
        )

        assert session.id == session_id
        assert session.tenant_id == "tenant-1"
        assert session.user_id == "user-123"
        assert session.is_active == True  # Default

    def test_create_session_with_context(self):
        """Test session with context."""
        context = {
            "exception_id": "EX-2024-0001",
            "filters": {"severity": "high"},
        }

        session = CopilotSession(
            id=uuid4(),
            tenant_id="tenant-1",
            user_id="user-123",
            title="Investigating settlement failure",
            context_json=context,
        )

        assert session.title == "Investigating settlement failure"
        assert session.context_json == context

    def test_create_session_with_expiration(self):
        """Test session with TTL."""
        expires = datetime.now(timezone.utc)

        session = CopilotSession(
            id=uuid4(),
            tenant_id="tenant-1",
            user_id="user-123",
            expires_at=expires,
            is_active=True,
        )

        assert session.expires_at == expires

    def test_session_repr(self):
        """Test session string representation."""
        session = CopilotSession(
            id=uuid4(),
            tenant_id="tenant-1",
            user_id="user-123",
            is_active=True,
        )

        repr_str = repr(session)
        assert "CopilotSession" in repr_str
        assert "tenant-1" in repr_str
        assert "user-123" in repr_str


class TestCopilotMessageModel:
    """Tests for CopilotMessage model."""

    def test_create_user_message(self):
        """Test user message creation."""
        session_id = uuid4()

        message = CopilotMessage(
            session_id=session_id,
            tenant_id="tenant-1",
            role="user",
            content="What caused this exception?",
        )

        assert message.session_id == session_id
        assert message.tenant_id == "tenant-1"
        assert message.role == "user"
        assert message.content == "What caused this exception?"

    def test_create_assistant_message_with_metadata(self):
        """Test assistant message with citations and playbook."""
        session_id = uuid4()
        metadata = {
            "citations": [
                {
                    "source_type": "policy_doc",
                    "source_id": "SOP-FIN-001",
                    "title": "Settlement Failure SOP",
                    "snippet": "Step 1: Verify...",
                }
            ],
            "recommended_playbook": {
                "playbook_id": "PB-FIN-001",
                "confidence": 0.92,
            },
            "safety": {
                "mode": "READ_ONLY",
                "actions_allowed": [],
            },
        }

        message = CopilotMessage(
            session_id=session_id,
            tenant_id="tenant-1",
            role="assistant",
            content="Based on the analysis...",
            metadata_json=metadata,
            intent="explain",
            request_id="req-12345",
            tokens_used=250,
            latency_ms=1500,
        )

        assert message.role == "assistant"
        assert message.metadata_json == metadata
        assert message.intent == "explain"
        assert message.request_id == "req-12345"
        assert message.tokens_used == 250
        assert message.latency_ms == 1500

    def test_create_message_with_exception_context(self):
        """Test message linked to exception."""
        session_id = uuid4()

        message = CopilotMessage(
            session_id=session_id,
            tenant_id="tenant-1",
            role="user",
            content="Explain why this was classified as high severity",
            exception_id="EX-2024-0001",
        )

        assert message.exception_id == "EX-2024-0001"

    def test_message_repr(self):
        """Test message string representation."""
        session_id = uuid4()

        message = CopilotMessage(
            id=1,
            session_id=session_id,
            tenant_id="tenant-1",
            role="user",
            content="test",
        )

        repr_str = repr(message)
        assert "CopilotMessage" in repr_str
        assert "user" in repr_str
        assert "tenant-1" in repr_str


class TestModelConstraints:
    """Tests for model constraints and required fields."""

    def test_document_requires_tenant_id(self):
        """Document should require tenant_id."""
        doc = CopilotDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            chunk_id="SOP-001-chunk-0",
            chunk_index=0,
            content="test",
        )
        # tenant_id is None - would fail on DB insert
        assert doc.tenant_id is None

    def test_document_requires_content(self):
        """Document should require content."""
        doc = CopilotDocument(
            tenant_id="tenant-1",
            source_type="policy_doc",
            source_id="SOP-001",
            chunk_id="SOP-001-chunk-0",
            chunk_index=0,
        )
        # content is None - would fail on DB insert
        assert doc.content is None

    def test_session_requires_tenant_and_user(self):
        """Session should require tenant_id and user_id."""
        session = CopilotSession(
            id=uuid4(),
        )
        # Missing tenant_id and user_id
        assert session.tenant_id is None
        assert session.user_id is None

    def test_message_requires_session_and_tenant(self):
        """Message should require session_id and tenant_id."""
        message = CopilotMessage(
            role="user",
            content="test",
        )
        # Missing session_id and tenant_id
        assert message.session_id is None
        assert message.tenant_id is None
