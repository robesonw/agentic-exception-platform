"""
Copilot Document Repository for Phase 13 Vector Storage.

Provides CRUD operations for vector-indexed documents with tenant isolation.
Supports similarity search using pgvector when available.

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2
- .github/ISSUE_TEMPLATE/phase13-copilot-intelligence-issues.md P13-1
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import CopilotDocument
from src.repository.base import AbstractBaseRepository, PaginatedResult, RepositoryError

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Data class for document chunk input."""
    source_type: str
    source_id: str
    chunk_id: str
    chunk_index: int
    content: str
    embedding: Optional[list[float]] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    domain: Optional[str] = None
    version: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class SimilarDocument:
    """Data class for similarity search result."""
    document: CopilotDocument
    similarity_score: float


class CopilotDocumentRepository(AbstractBaseRepository[CopilotDocument]):
    """
    Repository for Copilot vector-indexed documents.

    Provides:
    - CRUD operations with tenant isolation
    - Batch upsert for efficient indexing
    - Similarity search (pgvector)
    - Content deduplication via hash
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        super().__init__(session)

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[CopilotDocument]:
        """Get document by ID with tenant isolation."""
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(CopilotDocument).where(
            CopilotDocument.id == int(id),
            CopilotDocument.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> PaginatedResult[CopilotDocument]:
        """
        List documents for a tenant with pagination and filters.

        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed)
            page_size: Items per page
            source_type: Optional filter by source type
            source_id: Optional filter by source ID
            domain: Optional filter by domain

        Returns:
            PaginatedResult with documents
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(CopilotDocument).where(CopilotDocument.tenant_id == tenant_id)

        if source_type:
            query = query.where(CopilotDocument.source_type == source_type)
        if source_id:
            query = query.where(CopilotDocument.source_id == source_id)
        if domain:
            query = query.where(CopilotDocument.domain == domain)

        query = query.order_by(CopilotDocument.created_at.desc())

        return await self._execute_paginated(query, page, page_size)

    async def get_by_chunk_id(
        self,
        tenant_id: str,
        source_type: str,
        source_id: str,
        chunk_id: str,
    ) -> Optional[CopilotDocument]:
        """Get a specific chunk by its unique identifiers."""
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(CopilotDocument).where(
            CopilotDocument.tenant_id == tenant_id,
            CopilotDocument.source_type == source_type,
            CopilotDocument.source_id == source_id,
            CopilotDocument.chunk_id == chunk_id,
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_content_hash(
        self,
        tenant_id: str,
        content_hash: str,
    ) -> Optional[CopilotDocument]:
        """Get document by content hash for deduplication."""
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(CopilotDocument).where(
            CopilotDocument.tenant_id == tenant_id,
            CopilotDocument.content_hash == content_hash,
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute SHA-256 hash of content for deduplication."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def upsert_chunk(
        self,
        tenant_id: str,
        chunk: DocumentChunk,
    ) -> CopilotDocument:
        """
        Upsert a single document chunk.

        Creates or updates based on (tenant_id, source_type, source_id, chunk_id).

        Args:
            tenant_id: Tenant identifier
            chunk: Document chunk data

        Returns:
            Created or updated CopilotDocument
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        content_hash = self.compute_content_hash(chunk.content)

        # Check if exists
        existing = await self.get_by_chunk_id(
            tenant_id, chunk.source_type, chunk.source_id, chunk.chunk_id
        )

        if existing:
            # Update existing
            existing.content = chunk.content
            existing.embedding = chunk.embedding
            existing.embedding_model = chunk.embedding_model
            existing.embedding_dimension = chunk.embedding_dimension
            existing.domain = chunk.domain
            existing.version = chunk.version
            existing.metadata_json = chunk.metadata
            existing.content_hash = content_hash
            existing.chunk_index = chunk.chunk_index
            await self.session.flush()
            await self.session.refresh(existing)
            logger.debug(f"Updated document chunk: {chunk.chunk_id}")
            return existing
        else:
            # Create new
            doc = CopilotDocument(
                tenant_id=tenant_id,
                source_type=chunk.source_type,
                source_id=chunk.source_id,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                embedding=chunk.embedding,
                embedding_model=chunk.embedding_model,
                embedding_dimension=chunk.embedding_dimension,
                domain=chunk.domain,
                version=chunk.version,
                metadata_json=chunk.metadata,
                content_hash=content_hash,
            )
            self.session.add(doc)
            await self.session.flush()
            await self.session.refresh(doc)
            logger.debug(f"Created document chunk: {chunk.chunk_id}")
            return doc

    async def upsert_chunks_batch(
        self,
        tenant_id: str,
        chunks: list[DocumentChunk],
    ) -> int:
        """
        Batch upsert multiple document chunks.

        Uses PostgreSQL ON CONFLICT for efficient upsert.

        Args:
            tenant_id: Tenant identifier
            chunks: List of document chunks

        Returns:
            Number of chunks upserted
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        if not chunks:
            return 0

        values = []
        for chunk in chunks:
            content_hash = self.compute_content_hash(chunk.content)
            values.append({
                "tenant_id": tenant_id,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "embedding": chunk.embedding,
                "embedding_model": chunk.embedding_model,
                "embedding_dimension": chunk.embedding_dimension,
                "domain": chunk.domain,
                "version": chunk.version,
                "metadata_json": chunk.metadata,
                "content_hash": content_hash,
            })

        # Use PostgreSQL INSERT ... ON CONFLICT
        stmt = insert(CopilotDocument).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_copilot_doc_tenant_source_chunk",
            set_={
                "content": stmt.excluded.content,
                "embedding": stmt.excluded.embedding,
                "embedding_model": stmt.excluded.embedding_model,
                "embedding_dimension": stmt.excluded.embedding_dimension,
                "domain": stmt.excluded.domain,
                "version": stmt.excluded.version,
                "metadata_json": stmt.excluded.metadata_json,
                "content_hash": stmt.excluded.content_hash,
                "chunk_index": stmt.excluded.chunk_index,
                "updated_at": datetime.utcnow(),
            }
        )

        await self.session.execute(stmt)
        await self.session.flush()

        logger.info(f"Batch upserted {len(chunks)} document chunks for tenant {tenant_id}")
        return len(chunks)

    async def delete_by_source(
        self,
        tenant_id: str,
        source_type: str,
        source_id: str,
    ) -> int:
        """
        Delete all chunks for a source document.

        Args:
            tenant_id: Tenant identifier
            source_type: Source type
            source_id: Source document ID

        Returns:
            Number of chunks deleted
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        stmt = delete(CopilotDocument).where(
            CopilotDocument.tenant_id == tenant_id,
            CopilotDocument.source_type == source_type,
            CopilotDocument.source_id == source_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        count = result.rowcount
        logger.info(f"Deleted {count} chunks for source {source_type}/{source_id}")
        return count

    async def delete_by_tenant(self, tenant_id: str) -> int:
        """
        Delete all documents for a tenant (for rebuild operations).

        Args:
            tenant_id: Tenant identifier

        Returns:
            Number of documents deleted
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        stmt = delete(CopilotDocument).where(
            CopilotDocument.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        count = result.rowcount
        logger.warning(f"Deleted all {count} documents for tenant {tenant_id}")
        return count

    async def delete_by_source_type(
        self,
        tenant_id: str,
        source_type: str,
    ) -> int:
        """
        Delete all documents of a source type for a tenant.

        Args:
            tenant_id: Tenant identifier
            source_type: Source type to delete

        Returns:
            Number of documents deleted
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        stmt = delete(CopilotDocument).where(
            CopilotDocument.tenant_id == tenant_id,
            CopilotDocument.source_type == source_type,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        count = result.rowcount
        logger.info(f"Deleted {count} documents of type {source_type} for tenant {tenant_id}")
        return count

    async def similarity_search(
        self,
        tenant_id: str,
        query_embedding: list[float],
        limit: int = 10,
        source_type: Optional[str] = None,
        domain: Optional[str] = None,
        threshold: float = 0.0,
    ) -> list[SimilarDocument]:
        """
        Find similar documents using vector similarity search.

        Uses pgvector's cosine similarity when available.
        Falls back to exact computation for JSONB embeddings.

        Args:
            tenant_id: Tenant identifier
            query_embedding: Query vector
            limit: Maximum results to return
            source_type: Optional filter by source type
            domain: Optional filter by domain
            threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of SimilarDocument with scores, sorted by similarity descending
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        if not query_embedding:
            raise ValueError("query_embedding is required")

        # Build the similarity query using pgvector
        # Note: This requires the embedding column to be cast appropriately
        # We use cosine similarity: 1 - (embedding <=> query_vector)
        
        # Build WHERE clause
        where_clauses = ["tenant_id = :tenant_id", "embedding IS NOT NULL"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}

        if source_type:
            where_clauses.append("source_type = :source_type")
            params["source_type"] = source_type

        if domain:
            where_clauses.append("domain = :domain")
            params["domain"] = domain

        where_sql = " AND ".join(where_clauses)

        # Check if pgvector is available - if not, use fallback directly
        try:
            # Quick test to see if pgvector operations are available
            test_result = await self.session.execute(text("SELECT 1 WHERE 'vector' = ANY(SELECT extname FROM pg_extension)"))
            has_pgvector = test_result.fetchone() is not None
        except:
            has_pgvector = False

        if not has_pgvector:
            # Use Python-based fallback directly since pgvector is not available
            logger.info("pgvector not available, using Python fallback for similarity search")
            return await self._similarity_search_fallback(
                tenant_id, query_embedding, limit, source_type, domain, threshold
            )

        # Try pgvector query (only if extension is available)
        try:
            # pgvector cosine distance: 1 - (a <=> b) gives similarity
            # Format the vector as a proper array string
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            
            sql = text(f"""
                SELECT
                    id, tenant_id, source_type, source_id, domain, chunk_id,
                    chunk_index, content, embedding, embedding_model,
                    embedding_dimension, metadata_json, version, content_hash,
                    created_at, updated_at,
                    1 - (embedding <=> :query_vector) as similarity
                FROM copilot_documents
                WHERE {where_sql}
                ORDER BY embedding <=> :query_vector
                LIMIT :limit
            """)
            params["query_vector"] = embedding_str

            result = await self.session.execute(sql, params)
            rows = result.fetchall()

            similar_docs = []
            for row in rows:
                similarity = float(row.similarity) if row.similarity else 0.0
                if similarity >= threshold:
                    doc = CopilotDocument(
                        id=row.id,
                        tenant_id=row.tenant_id,
                        source_type=row.source_type,
                        source_id=row.source_id,
                        domain=row.domain,
                        chunk_id=row.chunk_id,
                        chunk_index=row.chunk_index,
                        content=row.content,
                        embedding=row.embedding,
                        embedding_model=row.embedding_model,
                        embedding_dimension=row.embedding_dimension,
                        metadata_json=row.metadata_json,
                        version=row.version,
                        content_hash=row.content_hash,
                        created_at=row.created_at,
                        updated_at=row.updated_at,
                    )
                    similar_docs.append(SimilarDocument(document=doc, similarity_score=similarity))

            return similar_docs

        except Exception as e:
            # Fallback: compute similarity in Python (less efficient)
            # Don't rollback the session as this should be handled by the context manager
            logger.warning(f"pgvector query failed, using fallback: {e}")
            return await self._similarity_search_fallback(
                tenant_id, query_embedding, limit, source_type, domain, threshold
            )

    async def _similarity_search_fallback(
        self,
        tenant_id: str,
        query_embedding: list[float],
        limit: int,
        source_type: Optional[str],
        domain: Optional[str],
        threshold: float,
    ) -> list[SimilarDocument]:
        """Fallback similarity search using Python computation."""
        query = select(CopilotDocument).where(
            CopilotDocument.tenant_id == tenant_id,
            CopilotDocument.embedding.isnot(None),
        )

        if source_type:
            query = query.where(CopilotDocument.source_type == source_type)
        if domain:
            query = query.where(CopilotDocument.domain == domain)

        result = await self.session.execute(query)
        docs = result.scalars().all()

        # Compute cosine similarity
        similar_docs = []
        for doc in docs:
            if doc.embedding:
                similarity = self._cosine_similarity(query_embedding, doc.embedding)
                if similarity >= threshold:
                    similar_docs.append(SimilarDocument(document=doc, similarity_score=similarity))

        # Sort by similarity descending and limit
        similar_docs.sort(key=lambda x: x.similarity_score, reverse=True)
        return similar_docs[:limit]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def count_by_tenant(self, tenant_id: str) -> int:
        """Count total documents for a tenant."""
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        from sqlalchemy import func
        query = select(func.count()).select_from(CopilotDocument).where(
            CopilotDocument.tenant_id == tenant_id
        )
        result = await self.session.execute(query)
        return result.scalar_one() or 0

    async def count_by_source_type(
        self,
        tenant_id: str,
        source_type: str,
    ) -> int:
        """Count documents by source type for a tenant."""
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        from sqlalchemy import func
        query = select(func.count()).select_from(CopilotDocument).where(
            CopilotDocument.tenant_id == tenant_id,
            CopilotDocument.source_type == source_type,
        )
        result = await self.session.execute(query)
        return result.scalar_one() or 0
