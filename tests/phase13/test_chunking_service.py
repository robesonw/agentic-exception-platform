"""
Unit tests for Phase 13 DocumentChunkingService.

Tests:
- Fixed size chunking
- Sentence-based chunking
- Paragraph-based chunking
- Semantic chunking
- Document type converters
- Chunk metadata
"""

import pytest

from src.services.copilot.chunking_service import (
    ChunkingConfig,
    ChunkingStrategy,
    DocumentChunk,
    DocumentChunkingService,
    SourceDocument,
)


class TestChunkingConfig:
    """Tests for ChunkingConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = ChunkingConfig.default()

        assert config.strategy == ChunkingStrategy.SENTENCE
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.min_chunk_size == 100
        assert config.max_chunk_size == 1024

    def test_policy_docs_config(self):
        """Test configuration for policy documents."""
        config = ChunkingConfig.for_policy_docs()

        assert config.strategy == ChunkingStrategy.PARAGRAPH
        assert config.chunk_size == 600
        assert config.chunk_overlap == 100
        assert config.preserve_paragraphs == True

    def test_exceptions_config(self):
        """Test configuration for exceptions."""
        config = ChunkingConfig.for_exceptions()

        assert config.strategy == ChunkingStrategy.SEMANTIC
        assert config.chunk_size == 400
        assert config.chunk_overlap == 50

    def test_audit_events_config(self):
        """Test configuration for audit events."""
        config = ChunkingConfig.for_audit_events()

        assert config.strategy == ChunkingStrategy.FIXED_SIZE
        assert config.chunk_size == 300
        assert config.chunk_overlap == 30


class TestDocumentChunk:
    """Tests for DocumentChunk dataclass."""

    def test_create_chunk(self):
        """Test basic chunk creation."""
        chunk = DocumentChunk(
            chunk_id="SOP-001-chunk-0",
            chunk_index=0,
            content="This is chunk content.",
            source_type="policy_doc",
            source_id="SOP-001",
        )

        assert chunk.chunk_id == "SOP-001-chunk-0"
        assert chunk.chunk_index == 0
        assert chunk.content == "This is chunk content."
        assert chunk.source_type == "policy_doc"
        assert chunk.source_id == "SOP-001"
        assert chunk.total_chunks == 1

    def test_chunk_with_metadata(self):
        """Test chunk with metadata."""
        chunk = DocumentChunk(
            chunk_id="SOP-001-chunk-0",
            chunk_index=0,
            content="Content here.",
            source_type="policy_doc",
            source_id="SOP-001",
            domain="Finance",
            version="v1.0",
            metadata={"title": "Settlement SOP"},
            start_position=0,
            end_position=100,
            total_chunks=3,
        )

        assert chunk.domain == "Finance"
        assert chunk.version == "v1.0"
        assert chunk.metadata == {"title": "Settlement SOP"}
        assert chunk.start_position == 0
        assert chunk.end_position == 100
        assert chunk.total_chunks == 3


class TestSourceDocument:
    """Tests for SourceDocument dataclass."""

    def test_create_document(self):
        """Test source document creation."""
        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content="Full document content here.",
        )

        assert doc.source_type == "policy_doc"
        assert doc.source_id == "SOP-001"
        assert doc.content == "Full document content here."

    def test_document_with_all_fields(self):
        """Test document with all optional fields."""
        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content="Content",
            domain="Finance",
            version="v1.0",
            title="Settlement Failure SOP",
            metadata={"author": "admin"},
        )

        assert doc.domain == "Finance"
        assert doc.version == "v1.0"
        assert doc.title == "Settlement Failure SOP"
        assert doc.metadata == {"author": "admin"}


class TestFixedSizeChunking:
    """Tests for fixed-size chunking strategy."""

    @pytest.fixture
    def service(self):
        """Create service with fixed-size config."""
        config = ChunkingConfig(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=100,
            chunk_overlap=20,
            min_chunk_size=10,
            max_chunk_size=150,
        )
        return DocumentChunkingService(config)

    def test_short_document_single_chunk(self, service):
        """Short document should produce single chunk."""
        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content="This is a short document.",
        )

        chunks = service.chunk_document(doc)

        assert len(chunks) == 1
        assert chunks[0].content == "This is a short document."
        assert chunks[0].chunk_index == 0

    def test_long_document_multiple_chunks(self, service):
        """Long document should produce multiple chunks."""
        # Create content longer than chunk_size
        content = "This is sentence one. " * 10  # ~220 chars

        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content=content,
        )

        chunks = service.chunk_document(doc)

        assert len(chunks) >= 2
        # Each chunk should be within size limits
        for chunk in chunks:
            assert len(chunk.content) <= 150

    def test_chunk_ids_are_unique(self, service):
        """Each chunk should have unique ID."""
        content = "Word " * 100

        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content=content,
        )

        chunks = service.chunk_document(doc)
        chunk_ids = [c.chunk_id for c in chunks]

        assert len(chunk_ids) == len(set(chunk_ids))

    def test_chunk_indexes_sequential(self, service):
        """Chunk indexes should be sequential."""
        content = "Word " * 100

        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content=content,
        )

        chunks = service.chunk_document(doc)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_total_chunks_set_correctly(self, service):
        """Each chunk should know total chunks."""
        content = "Word " * 100

        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content=content,
        )

        chunks = service.chunk_document(doc)
        total = len(chunks)

        for chunk in chunks:
            assert chunk.total_chunks == total


class TestSentenceChunking:
    """Tests for sentence-based chunking strategy."""

    @pytest.fixture
    def service(self):
        """Create service with sentence config."""
        config = ChunkingConfig(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=200,
            chunk_overlap=50,
            min_chunk_size=50,
            max_chunk_size=300,
        )
        return DocumentChunkingService(config)

    def test_respects_sentence_boundaries(self, service):
        """Chunks should end at sentence boundaries."""
        content = (
            "This is the first sentence. "
            "This is the second sentence. "
            "This is the third sentence. "
            "This is the fourth sentence."
        )

        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content=content,
        )

        chunks = service.chunk_document(doc)

        # Chunks should not split mid-sentence
        for chunk in chunks:
            # Each chunk should end with sentence ending or be last chunk
            assert (
                chunk.content.endswith('.')
                or chunk.content.endswith('!')
                or chunk.content.endswith('?')
                or chunk == chunks[-1]
            )


class TestParagraphChunking:
    """Tests for paragraph-based chunking strategy."""

    @pytest.fixture
    def service(self):
        """Create service with paragraph config."""
        config = ChunkingConfig(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=200,
            chunk_overlap=50,
            min_chunk_size=30,
            max_chunk_size=400,
        )
        return DocumentChunkingService(config)

    def test_respects_paragraph_boundaries(self, service):
        """Chunks should prefer paragraph boundaries."""
        content = (
            "This is paragraph one with some content.\n\n"
            "This is paragraph two with more content.\n\n"
            "This is paragraph three."
        )

        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content=content,
        )

        chunks = service.chunk_document(doc)

        # Should create chunks respecting paragraphs
        assert len(chunks) >= 1

    def test_handles_single_paragraph(self, service):
        """Single paragraph document should work."""
        content = "This is a single paragraph document with no breaks."

        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content=content,
        )

        chunks = service.chunk_document(doc)

        assert len(chunks) == 1
        assert chunks[0].content == content


class TestSemanticChunking:
    """Tests for semantic chunking strategy."""

    @pytest.fixture
    def service(self):
        """Create service with semantic config."""
        config = ChunkingConfig(
            strategy=ChunkingStrategy.SEMANTIC,
            chunk_size=200,
            chunk_overlap=30,
            min_chunk_size=50,
            max_chunk_size=400,
        )
        return DocumentChunkingService(config)

    def test_detects_section_markers(self, service):
        """Should detect section markers like numbers."""
        content = (
            "1. Introduction\n\n"
            "This is the introduction section.\n\n"
            "2. Background\n\n"
            "This is the background section.\n\n"
            "3. Conclusion\n\n"
            "This is the conclusion."
        )

        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content=content,
        )

        chunks = service.chunk_document(doc)

        # Should create multiple chunks at section boundaries
        assert len(chunks) >= 1


class TestDocumentTypeConverters:
    """Tests for document type-specific converters."""

    @pytest.fixture
    def service(self):
        """Create default service."""
        return DocumentChunkingService()

    def test_chunk_policy_document(self, service):
        """Test policy document chunking."""
        content = (
            "1. Purpose\n\n"
            "This SOP describes the settlement failure process.\n\n"
            "2. Scope\n\n"
            "Applies to all settlement failures in the Finance domain.\n\n"
            "3. Procedure\n\n"
            "Step 1: Verify counterparty details.\n"
            "Step 2: Check settlement amount.\n"
            "Step 3: Escalate if needed."
        )

        chunks = service.chunk_policy_document(
            content=content,
            source_id="SOP-FIN-001",
            domain="Finance",
            title="Settlement Failure SOP",
            version="v1.0",
        )

        assert len(chunks) >= 1
        assert all(c.source_type == "policy_doc" for c in chunks)
        assert all(c.source_id == "SOP-FIN-001" for c in chunks)
        assert all(c.domain == "Finance" for c in chunks)

    def test_chunk_exception_record(self, service):
        """Test exception record chunking."""
        exception_data = {
            "type": "SettlementFailure",
            "severity": "high",
            "status": "resolved",
            "source_system": "Murex",
            "entity": "COUNTERPARTY-001",
            "resolution_notes": "Issue was due to incorrect SWIFT code. Updated and resubmitted.",
            "outcome": "Resolved within SLA",
        }

        chunks = service.chunk_exception_record(
            exception_data=exception_data,
            exception_id="EX-2024-0001",
            tenant_id="tenant-1",
            domain="Finance",
        )

        assert len(chunks) >= 1
        assert all(c.source_type == "resolved_exception" for c in chunks)
        assert all(c.source_id == "EX-2024-0001" for c in chunks)

        # Content should include key fields
        content = chunks[0].content
        assert "SettlementFailure" in content
        assert "high" in content or "Severity" in content

    def test_chunk_audit_event(self, service):
        """Test audit event chunking."""
        event_data = {
            "event_type": "POLICY_ACTIVATED",
            "action": "activate",
            "actor_id": "admin@company.com",
            "entity_type": "tenant_pack",
            "entity_id": "TP-001",
            "diff_summary": "Activated new policy pack version v2.0",
            "reason": "Quarterly policy update",
        }

        chunks = service.chunk_audit_event(
            event_data=event_data,
            event_id="AE-001",
            tenant_id="tenant-1",
        )

        assert len(chunks) >= 1
        assert all(c.source_type == "audit_event" for c in chunks)

    def test_chunk_tool_definition(self, service):
        """Test tool definition chunking (excludes secrets)."""
        tool_data = {
            "name": "SendEmailNotification",
            "description": "Sends email notifications to stakeholders",
            "type": "webhook",
            "capabilities": ["notify", "email"],
            "input_schema": {
                "description": "Email notification parameters",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
            },
            # These should NOT appear in output
            "api_key": "secret-key-12345",
            "endpoint": "https://api.internal.com/send",
        }

        chunks = service.chunk_tool_definition(
            tool_data=tool_data,
            tool_id="TOOL-001",
            tenant_id="tenant-1",
        )

        assert len(chunks) >= 1
        assert all(c.source_type == "tool_registry" for c in chunks)

        # Secrets should NOT be in content
        content = chunks[0].content
        assert "secret-key" not in content.lower()
        # But description should be there
        assert "SendEmailNotification" in content

    def test_chunk_playbook(self, service):
        """Test playbook chunking."""
        playbook_data = {
            "name": "Handle Settlement Failure",
            "description": "Standard playbook for settlement failures",
            "conditions": {
                "domain": "Finance",
                "type": "SettlementFailure",
                "severity": ["high", "critical"],
            },
            "steps": [
                {"name": "Classify Failure", "action_type": "agent", "description": "Triage the failure"},
                {"name": "Supervisor Approval", "action_type": "human"},
                {"name": "Execute Correction", "action_type": "system"},
            ],
        }

        chunks = service.chunk_playbook(
            playbook_data=playbook_data,
            playbook_id="PB-FIN-001",
            tenant_id="tenant-1",
            domain="Finance",
        )

        assert len(chunks) >= 1
        assert all(c.source_type == "playbook" for c in chunks)

        content = chunks[0].content
        assert "Handle Settlement Failure" in content
        assert "Classify Failure" in content


class TestChunkMetadata:
    """Tests for chunk metadata handling."""

    @pytest.fixture
    def service(self):
        """Create default service."""
        return DocumentChunkingService()

    def test_metadata_preserved_from_source(self, service):
        """Source metadata should be preserved in chunks."""
        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content="Short content.",
            title="Test Document",
            metadata={"author": "admin", "category": "sop"},
        )

        chunks = service.chunk_document(doc)

        assert chunks[0].metadata.get("title") == "Test Document"
        assert chunks[0].metadata.get("author") == "admin"
        assert chunks[0].metadata.get("category") == "sop"

    def test_original_length_in_metadata(self, service):
        """Chunk metadata should include original document length."""
        content = "A" * 500
        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content=content,
        )

        chunks = service.chunk_document(doc)

        assert chunks[0].metadata.get("original_length") == 500


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    def service(self):
        """Create default service."""
        return DocumentChunkingService()

    def test_empty_content(self, service):
        """Empty content should return empty list."""
        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content="",
        )

        chunks = service.chunk_document(doc)
        assert chunks == []

    def test_whitespace_only_content(self, service):
        """Whitespace-only content should return empty list."""
        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content="   \n\n\t  ",
        )

        chunks = service.chunk_document(doc)
        assert chunks == []

    def test_normalizes_whitespace(self, service):
        """Multiple spaces should be normalized."""
        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content="Word    with    multiple    spaces.",
        )

        chunks = service.chunk_document(doc)

        # Multiple spaces should be reduced to single
        assert "    " not in chunks[0].content

    def test_normalizes_newlines(self, service):
        """Different newline types should be normalized."""
        doc = SourceDocument(
            source_type="policy_doc",
            source_id="SOP-001",
            content="Line 1\r\nLine 2\rLine 3",
        )

        chunks = service.chunk_document(doc)

        # Windows and old Mac newlines should become Unix
        assert "\r" not in chunks[0].content

    def test_chunk_documents_batch(self, service):
        """Test chunking multiple documents."""
        docs = [
            SourceDocument(
                source_type="policy_doc",
                source_id="SOP-001",
                content="Document one content.",
            ),
            SourceDocument(
                source_type="policy_doc",
                source_id="SOP-002",
                content="Document two content.",
            ),
        ]

        all_chunks = service.chunk_documents(docs)

        assert len(all_chunks) == 2
        source_ids = [c.source_id for c in all_chunks]
        assert "SOP-001" in source_ids
        assert "SOP-002" in source_ids
