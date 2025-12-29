"""
DocumentChunkingService for Phase 13 Copilot Intelligence.

Provides semantic-aware document chunking with:
- Multiple chunking strategies (fixed size, sentence, paragraph)
- Configurable chunk overlap for context preservation
- Source attribution preserved in chunks
- Support for different document types (policies, exceptions, audit events)

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2
- .github/ISSUE_TEMPLATE/phase13-copilot-intelligence-issues.md P13-3
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ChunkingStrategy(str, Enum):
    """Available chunking strategies."""
    FIXED_SIZE = "fixed_size"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SEMANTIC = "semantic"


@dataclass
class ChunkingConfig:
    """Configuration for document chunking."""
    strategy: ChunkingStrategy = ChunkingStrategy.SENTENCE
    chunk_size: int = 512  # Target chunk size in tokens/chars
    chunk_overlap: int = 50  # Overlap between chunks
    min_chunk_size: int = 100  # Minimum chunk size
    max_chunk_size: int = 1024  # Maximum chunk size
    preserve_paragraphs: bool = True  # Avoid splitting paragraphs if possible
    preserve_sentences: bool = True  # Avoid splitting sentences if possible

    @classmethod
    def default(cls) -> "ChunkingConfig":
        """Return default configuration."""
        return cls()

    @classmethod
    def for_policy_docs(cls) -> "ChunkingConfig":
        """Configuration optimized for policy documents."""
        return cls(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=600,
            chunk_overlap=100,
            preserve_paragraphs=True,
        )

    @classmethod
    def for_exceptions(cls) -> "ChunkingConfig":
        """Configuration optimized for exception records."""
        return cls(
            strategy=ChunkingStrategy.SEMANTIC,
            chunk_size=400,
            chunk_overlap=50,
            preserve_sentences=True,
        )

    @classmethod
    def for_audit_events(cls) -> "ChunkingConfig":
        """Configuration optimized for audit events."""
        return cls(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=300,
            chunk_overlap=30,
        )


@dataclass
class DocumentChunk:
    """A chunk of a document with metadata."""
    chunk_id: str
    chunk_index: int
    content: str
    source_type: str
    source_id: str
    domain: Optional[str] = None
    version: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    start_position: int = 0
    end_position: int = 0
    total_chunks: int = 1


@dataclass
class SourceDocument:
    """Input document to be chunked."""
    source_type: str
    source_id: str
    content: str
    domain: Optional[str] = None
    version: Optional[str] = None
    title: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class DocumentChunkingService:
    """
    Service for chunking documents into semantic units.

    Features:
    - Multiple chunking strategies
    - Configurable overlap for context preservation
    - Source attribution in each chunk
    - Support for different document types
    """

    # Sentence boundary patterns
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
    PARAGRAPH_BOUNDARY = re.compile(r'\n\s*\n')

    def __init__(self, config: Optional[ChunkingConfig] = None):
        """
        Initialize chunking service.

        Args:
            config: Optional configuration (uses defaults if not provided)
        """
        self.config = config or ChunkingConfig.default()

    def chunk_document(self, document: SourceDocument) -> list[DocumentChunk]:
        """
        Chunk a document into smaller pieces.

        Args:
            document: Source document to chunk

        Returns:
            List of DocumentChunk objects with metadata
        """
        content = self._normalize_text(document.content)

        if not content:
            return []

        if self.config.strategy == ChunkingStrategy.FIXED_SIZE:
            chunks = self._chunk_fixed_size(content)
        elif self.config.strategy == ChunkingStrategy.SENTENCE:
            chunks = self._chunk_by_sentence(content)
        elif self.config.strategy == ChunkingStrategy.PARAGRAPH:
            chunks = self._chunk_by_paragraph(content)
        elif self.config.strategy == ChunkingStrategy.SEMANTIC:
            chunks = self._chunk_semantic(content)
        else:
            chunks = self._chunk_fixed_size(content)

        # Build DocumentChunk objects
        result = []
        total_chunks = len(chunks)

        for i, (chunk_content, start_pos, end_pos) in enumerate(chunks):
            chunk_id = f"{document.source_id}-chunk-{i}"

            chunk = DocumentChunk(
                chunk_id=chunk_id,
                chunk_index=i,
                content=chunk_content,
                source_type=document.source_type,
                source_id=document.source_id,
                domain=document.domain,
                version=document.version,
                metadata={
                    "title": document.title,
                    "original_length": len(content),
                    **(document.metadata or {}),
                },
                start_position=start_pos,
                end_position=end_pos,
                total_chunks=total_chunks,
            )
            result.append(chunk)

        logger.debug(
            f"Chunked document {document.source_id} into {len(result)} chunks "
            f"(strategy={self.config.strategy.value})"
        )

        return result

    def chunk_documents(self, documents: list[SourceDocument]) -> list[DocumentChunk]:
        """
        Chunk multiple documents.

        Args:
            documents: List of source documents

        Returns:
            Flattened list of all chunks
        """
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)

        logger.info(f"Chunked {len(documents)} documents into {len(all_chunks)} total chunks")
        return all_chunks

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent chunking."""
        if not text:
            return ""

        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)

        # Normalize newlines
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def _chunk_fixed_size(self, content: str) -> list[tuple[str, int, int]]:
        """
        Chunk by fixed character size with overlap.

        Returns list of (chunk_text, start_pos, end_pos) tuples.
        """
        chunks = []
        start = 0
        content_len = len(content)

        while start < content_len:
            end = min(start + self.config.chunk_size, content_len)

            # If not at end and we can preserve word boundaries
            if end < content_len and self.config.preserve_sentences:
                # Find last space before end
                last_space = content.rfind(' ', start, end)
                if last_space > start + self.config.min_chunk_size:
                    end = last_space

            chunk_text = content[start:end].strip()

            if len(chunk_text) >= self.config.min_chunk_size or start == 0:
                chunks.append((chunk_text, start, end))

            # Move start with overlap
            start = end - self.config.chunk_overlap
            if start >= content_len:
                break
            if start < 0:
                start = 0

        return chunks

    def _chunk_by_sentence(self, content: str) -> list[tuple[str, int, int]]:
        """
        Chunk by sentence boundaries.

        Combines sentences to reach target chunk size.
        """
        # Split into sentences
        sentences = self.SENTENCE_ENDINGS.split(content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return self._chunk_fixed_size(content)

        chunks = []
        current_chunk = []
        current_length = 0
        chunk_start = 0
        current_position = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            # If adding this sentence would exceed max size
            if current_length + sentence_len > self.config.max_chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append((chunk_text, chunk_start, current_position))

                # Start new chunk with overlap (last sentence)
                if self.config.chunk_overlap > 0 and len(current_chunk) > 0:
                    overlap_text = current_chunk[-1]
                    current_chunk = [overlap_text]
                    current_length = len(overlap_text)
                    chunk_start = current_position - len(overlap_text)
                else:
                    current_chunk = []
                    current_length = 0
                    chunk_start = current_position

            current_chunk.append(sentence)
            current_length += sentence_len + 1  # +1 for space
            current_position += sentence_len + 1

        # Add remaining content
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text) >= self.config.min_chunk_size or len(chunks) == 0:
                chunks.append((chunk_text, chunk_start, current_position))
            elif chunks:
                # Append to last chunk if too small
                last_chunk, last_start, _ = chunks[-1]
                chunks[-1] = (last_chunk + ' ' + chunk_text, last_start, current_position)

        return chunks

    def _chunk_by_paragraph(self, content: str) -> list[tuple[str, int, int]]:
        """
        Chunk by paragraph boundaries.

        Keeps paragraphs together when possible.
        """
        # Split into paragraphs
        paragraphs = self.PARAGRAPH_BOUNDARY.split(content)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if not paragraphs:
            return self._chunk_fixed_size(content)

        chunks = []
        current_chunk = []
        current_length = 0
        chunk_start = 0
        current_position = 0

        for para in paragraphs:
            para_len = len(para)

            # If single paragraph exceeds max, chunk it by sentence
            if para_len > self.config.max_chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append((chunk_text, chunk_start, current_position))
                    current_chunk = []
                    current_length = 0
                    chunk_start = current_position

                # Chunk the large paragraph by sentence
                para_chunks = self._chunk_by_sentence(para)
                for chunk_text, start, end in para_chunks:
                    chunks.append((chunk_text, current_position + start, current_position + end))

                current_position += para_len + 2  # +2 for paragraph break
                chunk_start = current_position
                continue

            # If adding this paragraph would exceed max size
            if current_length + para_len > self.config.max_chunk_size and current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append((chunk_text, chunk_start, current_position))
                current_chunk = []
                current_length = 0
                chunk_start = current_position

            current_chunk.append(para)
            current_length += para_len + 2  # +2 for paragraph break
            current_position += para_len + 2

        # Add remaining content
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append((chunk_text, chunk_start, current_position))

        return chunks

    def _chunk_semantic(self, content: str) -> list[tuple[str, int, int]]:
        """
        Semantic chunking - attempts to find logical boundaries.

        Combines paragraph and sentence strategies with heuristics.
        """
        # First try paragraph chunking
        paragraphs = self.PARAGRAPH_BOUNDARY.split(content)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if len(paragraphs) <= 1:
            # No paragraph structure, use sentence chunking
            return self._chunk_by_sentence(content)

        # Look for semantic section markers
        section_markers = re.compile(
            r'^(?:\d+\.|[A-Z]\.|[-*]|\#{1,6}|Section|Chapter|Part)\s',
            re.MULTILINE
        )

        chunks = []
        current_section = []
        current_length = 0
        chunk_start = 0
        current_position = 0

        for para in paragraphs:
            para_len = len(para)

            # Check if this paragraph starts a new section
            is_section_start = bool(section_markers.match(para))

            # Start new chunk on section boundaries if current is large enough
            if is_section_start and current_length >= self.config.min_chunk_size:
                chunk_text = '\n\n'.join(current_section)
                chunks.append((chunk_text, chunk_start, current_position))
                current_section = []
                current_length = 0
                chunk_start = current_position

            # Handle oversized paragraphs
            if para_len > self.config.max_chunk_size:
                if current_section:
                    chunk_text = '\n\n'.join(current_section)
                    chunks.append((chunk_text, chunk_start, current_position))
                    current_section = []
                    current_length = 0
                    chunk_start = current_position

                # Split large paragraph
                para_chunks = self._chunk_by_sentence(para)
                for chunk_text, start, end in para_chunks:
                    chunks.append((chunk_text, current_position + start, current_position + end))

                current_position += para_len + 2
                chunk_start = current_position
                continue

            # Check chunk size limit
            if current_length + para_len > self.config.max_chunk_size and current_section:
                chunk_text = '\n\n'.join(current_section)
                chunks.append((chunk_text, chunk_start, current_position))
                current_section = []
                current_length = 0
                chunk_start = current_position

            current_section.append(para)
            current_length += para_len + 2
            current_position += para_len + 2

        # Add remaining content
        if current_section:
            chunk_text = '\n\n'.join(current_section)
            chunks.append((chunk_text, chunk_start, current_position))

        return chunks

    # =========================================================================
    # Document Type Specific Converters
    # =========================================================================

    def chunk_policy_document(
        self,
        content: str,
        source_id: str,
        domain: Optional[str] = None,
        title: Optional[str] = None,
        version: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[DocumentChunk]:
        """
        Chunk a policy document with optimized settings.

        Args:
            content: Policy document text
            source_id: Document identifier (e.g., SOP-FIN-001)
            domain: Domain name
            title: Document title
            version: Document version
            metadata: Additional metadata

        Returns:
            List of DocumentChunk objects
        """
        # Use paragraph-optimized config
        original_config = self.config
        self.config = ChunkingConfig.for_policy_docs()

        try:
            doc = SourceDocument(
                source_type="policy_doc",
                source_id=source_id,
                content=content,
                domain=domain,
                version=version,
                title=title,
                metadata=metadata,
            )
            return self.chunk_document(doc)
        finally:
            self.config = original_config

    def chunk_exception_record(
        self,
        exception_data: dict[str, Any],
        exception_id: str,
        tenant_id: str,
        domain: Optional[str] = None,
    ) -> list[DocumentChunk]:
        """
        Convert and chunk an exception record.

        Converts structured exception JSON to text for embedding.

        Args:
            exception_data: Exception record as dict
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            domain: Domain name

        Returns:
            List of DocumentChunk objects
        """
        # Convert exception to text representation
        text_parts = []

        if exception_data.get("type"):
            text_parts.append(f"Exception Type: {exception_data['type']}")

        if exception_data.get("severity"):
            text_parts.append(f"Severity: {exception_data['severity']}")

        if exception_data.get("status"):
            text_parts.append(f"Status: {exception_data['status']}")

        if exception_data.get("source_system"):
            text_parts.append(f"Source: {exception_data['source_system']}")

        if exception_data.get("entity"):
            text_parts.append(f"Entity: {exception_data['entity']}")

        # Include resolution notes if present
        if exception_data.get("resolution_notes"):
            text_parts.append(f"\nResolution Notes:\n{exception_data['resolution_notes']}")

        # Include any description or summary
        if exception_data.get("description"):
            text_parts.append(f"\nDescription:\n{exception_data['description']}")

        # Include outcome
        if exception_data.get("outcome"):
            text_parts.append(f"\nOutcome: {exception_data['outcome']}")

        content = '\n'.join(text_parts)

        # Use exception-optimized config
        original_config = self.config
        self.config = ChunkingConfig.for_exceptions()

        try:
            doc = SourceDocument(
                source_type="resolved_exception",
                source_id=exception_id,
                content=content,
                domain=domain,
                metadata={
                    "tenant_id": tenant_id,
                    "severity": exception_data.get("severity"),
                    "status": exception_data.get("status"),
                    "type": exception_data.get("type"),
                },
            )
            return self.chunk_document(doc)
        finally:
            self.config = original_config

    def chunk_audit_event(
        self,
        event_data: dict[str, Any],
        event_id: str,
        tenant_id: str,
        domain: Optional[str] = None,
    ) -> list[DocumentChunk]:
        """
        Convert and chunk an audit event.

        Args:
            event_data: Audit event as dict
            event_id: Event identifier
            tenant_id: Tenant identifier
            domain: Domain name

        Returns:
            List of DocumentChunk objects
        """
        # Convert audit event to text
        text_parts = []

        if event_data.get("event_type"):
            text_parts.append(f"Event: {event_data['event_type']}")

        if event_data.get("action"):
            text_parts.append(f"Action: {event_data['action']}")

        if event_data.get("actor_id"):
            text_parts.append(f"Actor: {event_data['actor_id']}")

        if event_data.get("entity_type"):
            text_parts.append(f"Entity Type: {event_data['entity_type']}")

        if event_data.get("entity_id"):
            text_parts.append(f"Entity ID: {event_data['entity_id']}")

        if event_data.get("diff_summary"):
            text_parts.append(f"\nChange Summary:\n{event_data['diff_summary']}")

        if event_data.get("reason"):
            text_parts.append(f"\nReason: {event_data['reason']}")

        content = '\n'.join(text_parts)

        # Use audit-optimized config
        original_config = self.config
        self.config = ChunkingConfig.for_audit_events()

        try:
            doc = SourceDocument(
                source_type="audit_event",
                source_id=event_id,
                content=content,
                domain=domain,
                metadata={
                    "tenant_id": tenant_id,
                    "event_type": event_data.get("event_type"),
                    "action": event_data.get("action"),
                },
            )
            return self.chunk_document(doc)
        finally:
            self.config = original_config

    def chunk_tool_definition(
        self,
        tool_data: dict[str, Any],
        tool_id: str,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> list[DocumentChunk]:
        """
        Convert and chunk a tool definition (without secrets).

        Args:
            tool_data: Tool definition as dict
            tool_id: Tool identifier
            tenant_id: Tenant identifier (None for global tools)
            domain: Domain name

        Returns:
            List of DocumentChunk objects
        """
        # Convert tool to text (EXCLUDE secrets)
        text_parts = []

        if tool_data.get("name"):
            text_parts.append(f"Tool: {tool_data['name']}")

        if tool_data.get("description"):
            text_parts.append(f"Description: {tool_data['description']}")

        if tool_data.get("type"):
            text_parts.append(f"Type: {tool_data['type']}")

        if tool_data.get("capabilities"):
            text_parts.append(f"Capabilities: {', '.join(tool_data['capabilities'])}")

        # Include input schema description (not the actual schema for brevity)
        if tool_data.get("input_schema"):
            schema = tool_data["input_schema"]
            if schema.get("description"):
                text_parts.append(f"\nInput: {schema['description']}")
            if schema.get("properties"):
                props = list(schema["properties"].keys())
                text_parts.append(f"Parameters: {', '.join(props)}")

        content = '\n'.join(text_parts)

        doc = SourceDocument(
            source_type="tool_registry",
            source_id=str(tool_id),
            content=content,
            domain=domain,
            metadata={
                "tenant_id": tenant_id,
                "tool_name": tool_data.get("name"),
                "tool_type": tool_data.get("type"),
            },
        )
        return self.chunk_document(doc)

    def chunk_playbook(
        self,
        playbook_data: dict[str, Any],
        playbook_id: str,
        tenant_id: str,
        domain: Optional[str] = None,
    ) -> list[DocumentChunk]:
        """
        Convert and chunk a playbook definition.

        Args:
            playbook_data: Playbook as dict
            playbook_id: Playbook identifier
            tenant_id: Tenant identifier
            domain: Domain name

        Returns:
            List of DocumentChunk objects
        """
        text_parts = []

        if playbook_data.get("name"):
            text_parts.append(f"Playbook: {playbook_data['name']}")

        if playbook_data.get("description"):
            text_parts.append(f"Description: {playbook_data['description']}")

        # Include conditions/triggers
        if playbook_data.get("conditions"):
            conditions = playbook_data["conditions"]
            if isinstance(conditions, dict):
                cond_parts = []
                for key, value in conditions.items():
                    cond_parts.append(f"  - {key}: {value}")
                text_parts.append("Triggers:\n" + '\n'.join(cond_parts))

        # Include steps
        if playbook_data.get("steps"):
            text_parts.append("\nSteps:")
            for i, step in enumerate(playbook_data["steps"], 1):
                step_name = step.get("name", f"Step {i}")
                step_action = step.get("action_type", "unknown")
                text_parts.append(f"  {i}. {step_name} ({step_action})")
                if step.get("description"):
                    text_parts.append(f"     {step['description']}")

        content = '\n'.join(text_parts)

        doc = SourceDocument(
            source_type="playbook",
            source_id=str(playbook_id),
            content=content,
            domain=domain,
            metadata={
                "tenant_id": tenant_id,
                "playbook_name": playbook_data.get("name"),
                "step_count": len(playbook_data.get("steps", [])),
            },
        )
        return self.chunk_document(doc)
