#!/usr/bin/env python
"""
Index data for Copilot RAG.

This script indexes exceptions, playbooks, and tools into the copilot_documents
table so the Copilot can retrieve relevant evidence when answering questions.

Usage:
    python scripts/index_copilot_data.py --tenant TENANT_FINANCE_001
    python scripts/index_copilot_data.py --tenant TENANT_FINANCE_001 --source playbooks
    python scripts/index_copilot_data.py --all-tenants
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.models import (
    Exception as ExceptionModel,
    Playbook,
    PlaybookStep,
    ToolDefinition,
    Tenant,
)
from src.services.copilot.embedding_service import EmbeddingService
from src.services.copilot.chunking_service import DocumentChunkingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def get_db_session():
    """Create database session."""
    # Load from environment or use defaults
    import os
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai"
    )
    
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    return async_session()


async def index_exceptions(session: AsyncSession, tenant_id: str, doc_repo: CopilotDocumentRepository, embedding_service: EmbeddingService):
    """Index resolved exceptions for a tenant."""
    logger.info(f"Indexing exceptions for tenant: {tenant_id}")
    
    # Get exceptions for this tenant
    query = select(ExceptionModel).where(ExceptionModel.tenant_id == tenant_id)
    result = await session.execute(query)
    exceptions = result.scalars().all()
    
    logger.info(f"Found {len(exceptions)} exceptions to index")
    
    indexed_count = 0
    for exc in exceptions:
        try:
            # Create searchable text content
            # Note: ORM model uses 'type' not 'exception_type'
            content_parts = [
                f"Exception ID: {exc.exception_id}",
                f"Type: {exc.type or 'Unknown'}",
                f"Status: {exc.status or 'Unknown'}",
                f"Severity: {exc.severity or 'Unknown'}",
            ]
            
            # Add additional fields if available  
            if exc.source_system:
                content_parts.append(f"Source System: {exc.source_system}")
            if exc.domain:
                content_parts.append(f"Domain: {exc.domain}")
            if exc.entity:
                content_parts.append(f"Entity: {exc.entity}")
            
            content = "\n".join(content_parts)
            
            # Generate embedding
            embedding_result = await embedding_service.generate_embedding(content)
            
            # Create document chunk
            from src.infrastructure.repositories.copilot_document_repository import DocumentChunk
            chunk = DocumentChunk(
                source_type="resolved_exception",
                source_id=str(exc.exception_id),
                chunk_id=f"exc-{exc.exception_id}-0",
                chunk_index=0,
                content=content,
                embedding=embedding_result.embedding,
                embedding_model=embedding_result.model,
                embedding_dimension=embedding_result.dimension,
                domain=exc.domain,
                version="1",
                metadata={
                    "exception_id": str(exc.exception_id),
                    "exception_type": exc.type,
                    "status": str(exc.status) if exc.status else None,
                    "severity": str(exc.severity) if exc.severity else None,
                }
            )
            
            # Store in repository
            await doc_repo.upsert_chunks_batch(tenant_id, [chunk])
            indexed_count += 1
            
            if indexed_count % 10 == 0:
                logger.info(f"  Indexed {indexed_count}/{len(exceptions)} exceptions...")
                
        except Exception as e:
            logger.error(f"Failed to index exception {exc.exception_id}: {e}")
    
    await session.commit()
    logger.info(f"✓ Indexed {indexed_count} exceptions for {tenant_id}")
    return indexed_count


async def index_playbooks(session: AsyncSession, tenant_id: str, doc_repo: CopilotDocumentRepository, embedding_service: EmbeddingService):
    """Index playbooks for a tenant."""
    logger.info(f"Indexing playbooks for tenant: {tenant_id}")
    
    # Get playbooks for this tenant
    query = select(Playbook).where(Playbook.tenant_id == tenant_id)
    result = await session.execute(query)
    playbooks = result.scalars().all()
    
    logger.info(f"Found {len(playbooks)} playbooks to index")
    
    indexed_count = 0
    for pb in playbooks:
        try:
            # Get playbook steps
            steps_query = select(PlaybookStep).where(
                PlaybookStep.playbook_id == pb.playbook_id
            ).order_by(PlaybookStep.step_order)
            steps_result = await session.execute(steps_query)
            steps = steps_result.scalars().all()
            
            # Create searchable text content
            content_parts = [
                f"Playbook: {pb.name}",
                f"Playbook ID: {pb.playbook_id}",
            ]
            
            # Add conditions/metadata
            conditions = pb.conditions or {}
            if conditions.get("description"):
                content_parts.append(f"Description: {conditions['description']}")
            if conditions.get("exception_types"):
                content_parts.append(f"Handles exception types: {', '.join(conditions['exception_types'])}")
            if conditions.get("severities"):
                content_parts.append(f"Applicable severities: {', '.join(conditions['severities'])}")
            
            # Add steps
            if steps:
                content_parts.append("\nPlaybook Steps:")
                for step in steps:
                    content_parts.append(f"  Step {step.step_order}: {step.name} ({step.action_type})")
            
            content = "\n".join(content_parts)
            
            # Generate embedding
            embedding_result = await embedding_service.generate_embedding(content)
            
            # Create document chunk
            from src.infrastructure.repositories.copilot_document_repository import DocumentChunk
            chunk = DocumentChunk(
                source_type="playbook",
                source_id=str(pb.playbook_id),
                chunk_id=f"pb-{pb.playbook_id}-0",
                chunk_index=0,
                content=content,
                embedding=embedding_result.embedding,
                embedding_model=embedding_result.model,
                embedding_dimension=embedding_result.dimension,
                domain=None,  # Playbooks may span domains
                version=str(pb.version) if pb.version else "1",
                metadata={
                    "playbook_id": str(pb.playbook_id),
                    "name": pb.name,
                    "steps_count": len(steps),
                    "exception_types": conditions.get("exception_types", []),
                }
            )
            
            # Store in repository
            await doc_repo.upsert_chunks_batch(tenant_id, [chunk])
            indexed_count += 1
            
        except Exception as e:
            logger.error(f"Failed to index playbook {pb.playbook_id}: {e}")
    
    await session.commit()
    logger.info(f"✓ Indexed {indexed_count} playbooks for {tenant_id}")
    return indexed_count


async def index_tools(session: AsyncSession, tenant_id: str, doc_repo: CopilotDocumentRepository, embedding_service: EmbeddingService):
    """Index tool definitions for a tenant."""
    logger.info(f"Indexing tools for tenant: {tenant_id}")
    
    # Get tools - tools may be global or tenant-specific
    query = select(ToolDefinition)
    result = await session.execute(query)
    tools = result.scalars().all()
    
    logger.info(f"Found {len(tools)} tools to index")
    
    indexed_count = 0
    for tool in tools:
        try:
            # Create searchable text content
            # Note: ORM uses 'type' not 'tool_type', and config JSON for details
            content_parts = [
                f"Tool: {tool.name}",
                f"Tool ID: {tool.tool_id}",
            ]
            
            # Get description from config if available
            config = tool.config or {}
            if config.get("description"):
                content_parts.append(f"Description: {config['description']}")
            if tool.type:
                content_parts.append(f"Type: {tool.type}")
            if config.get("category"):
                content_parts.append(f"Category: {config['category']}")
            
            # Add parameter info if available
            params = config.get("input_schema") or config.get("parameters") or {}
            if params.get("properties"):
                content_parts.append("Parameters:")
                for param_name, param_info in params["properties"].items():
                    desc = param_info.get("description", "")
                    content_parts.append(f"  - {param_name}: {desc}")
            
            content = "\n".join(content_parts)
            
            # Generate embedding
            embedding_result = await embedding_service.generate_embedding(content)
            
            # Create document chunk
            from src.infrastructure.repositories.copilot_document_repository import DocumentChunk
            chunk = DocumentChunk(
                source_type="tool_registry",
                source_id=str(tool.tool_id),
                chunk_id=f"tool-{tool.tool_id}-0",
                chunk_index=0,
                content=content,
                embedding=embedding_result.embedding,
                embedding_model=embedding_result.model,
                embedding_dimension=embedding_result.dimension,
                domain=None,
                version="1",
                metadata={
                    "tool_id": str(tool.tool_id),
                    "name": tool.name,
                    "tool_type": tool.type,
                    "category": config.get("category"),
                }
            )
            
            # Store in repository
            await doc_repo.upsert_chunks_batch(tenant_id, [chunk])
            indexed_count += 1
            
        except Exception as e:
            logger.error(f"Failed to index tool {tool.tool_id}: {e}")
    
    await session.commit()
    logger.info(f"✓ Indexed {indexed_count} tools for {tenant_id}")
    return indexed_count


async def main():
    parser = argparse.ArgumentParser(description="Index data for Copilot RAG")
    parser.add_argument("--tenant", type=str, help="Tenant ID to index (e.g., TENANT_FINANCE_001)")
    parser.add_argument("--all-tenants", action="store_true", help="Index for all tenants")
    parser.add_argument("--source", type=str, choices=["exceptions", "playbooks", "tools", "all"], 
                        default="all", help="What to index")
    
    args = parser.parse_args()
    
    if not args.tenant and not args.all_tenants:
        parser.error("Either --tenant or --all-tenants must be specified")
    
    logger.info("=" * 60)
    logger.info("Copilot Data Indexer")
    logger.info("=" * 60)
    
    session = await get_db_session()
    
    try:
        # Initialize services
        embedding_service = EmbeddingService()
        doc_repo = CopilotDocumentRepository(session)
        
        # Get tenants to process
        if args.all_tenants:
            query = select(Tenant)
            result = await session.execute(query)
            tenants = [t.tenant_id for t in result.scalars().all()]
        else:
            tenants = [args.tenant]
        
        logger.info(f"Processing tenants: {tenants}")
        
        total_indexed = 0
        for tenant_id in tenants:
            logger.info(f"\n--- Processing tenant: {tenant_id} ---")
            
            if args.source in ["exceptions", "all"]:
                total_indexed += await index_exceptions(session, tenant_id, doc_repo, embedding_service)
            
            if args.source in ["playbooks", "all"]:
                total_indexed += await index_playbooks(session, tenant_id, doc_repo, embedding_service)
            
            if args.source in ["tools", "all"]:
                total_indexed += await index_tools(session, tenant_id, doc_repo, embedding_service)
        
        logger.info("\n" + "=" * 60)
        logger.info(f"✓ Indexing complete! Total documents indexed: {total_indexed}")
        logger.info("=" * 60)
        
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
