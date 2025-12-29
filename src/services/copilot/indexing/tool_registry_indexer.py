"""
ToolRegistryIndexer for Phase 13 Copilot Intelligence.

Indexes tool capabilities and descriptions for Similar Cases RAG retrieval.
Explicitly redacts sensitive configuration data (keys, secrets, tokens, etc.).

Cross-reference:
- docs/phase13-copilot-intelligence-mvp.md (ToolRegistry indexing)
- tasks: P13-7 (ToolRegistryIndexer), P13-8 (redaction)
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    ToolDefinition,
    CopilotDocumentSourceType,
)
from src.services.copilot.chunking_service import DocumentChunkingService, SourceDocument
from src.services.copilot.embedding_service import EmbeddingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from src.services.copilot.indexing.base import BaseIndexer, IndexingError
from src.services.copilot.indexing.types import IndexingResult
from src.services.copilot.indexing.utils import content_hash, validate_tenant_id

logger = logging.getLogger(__name__)


# Sensitive field patterns for redaction
SENSITIVE_FIELD_PATTERNS = {
    # Direct field names  
    "key", "keys", "secret", "secrets", "token", "tokens", "auth", "authentication",
    "password", "pass", "pwd", "credential", "credentials", "authorization",
    "api_key", "apikey", "access_key", "secret_key", "private_key", "public_key",
    "oauth", "oauth_token", "bearer", "bearer_token", "jwt", "session",
    "connection_string", "conn_str", "database_url", "db_url", "dsn",
    "cookie", "cookies", "signature", "cert", "certificate",
    
    # Pattern-based matches
    r".*_key$", r".*_secret$", r".*_token$", r".*_auth$", r".*_cred.*$",
    r".*password.*", r".*secret.*", r".*token.*", r".*auth.*", 
    r"x-.*-key", r"x-.*-secret", r"x-.*-token", r"authorization.*",
}

# Sensitive header names (for special header processing)
SENSITIVE_HEADERS = {
    "authorization", "auth", "authentication", "bearer", "token", "api-key", 
    "x-api-key", "x-auth-token", "x-access-token", "cookie", "set-cookie",
}

# Sensitive value patterns (for checking values even if field name is safe)
SENSITIVE_VALUE_PATTERNS = [
    r"^[A-Za-z0-9+/=]{32,}$",  # Base64-like strings (32+ chars)
    r"^[A-Za-z0-9-_]{40,}$",   # Token-like strings (40+ chars)
    r"^(sk-|pk-|ak-)",         # Common key prefixes
    r"^Bearer\s+",             # Bearer tokens
    r"^Basic\s+",              # Basic auth
    r"^[a-f0-9]{32,}$",        # Hex strings (32+ chars)
    r"postgres://.*",          # Connection strings
    r"mysql://.*",
    r"mongodb://.*",
    r"redis://.*",
    r"https?://.*@.*",         # URLs with auth
]


@dataclass
class ToolRegistryDoc:
    """
    Tool registry document for indexing (redacted of sensitive data).
    
    Contains only safe metadata about tool capabilities and descriptions,
    with all sensitive configuration data removed.
    """
    tool_id: str
    tenant_id: Optional[str]  # None for global tools
    name: str
    type: str
    safe_config: Dict[str, Any]  # Redacted configuration
    capabilities: List[str]  # Extracted tool capabilities
    description: Optional[str]  # Tool description from config
    created_at: datetime
    metadata: Optional[dict] = None

    def to_source_document(self) -> SourceDocument:
        """Convert tool registry entry to source document for indexing."""
        # Build content text from safe tool information
        content_parts = [
            f"Tool Name: {self.name}",
            f"Tool Type: {self.type}",
        ]
        
        if self.description:
            content_parts.append(f"Description: {self.description}")
        
        if self.capabilities:
            content_parts.append(f"Capabilities: {', '.join(self.capabilities)}")
        
        # Add safe configuration details (non-sensitive)
        if self.safe_config:
            safe_details = []
            for key, value in self.safe_config.items():
                if isinstance(value, (str, int, float, bool)):
                    safe_details.append(f"{key}: {value}")
                elif isinstance(value, list) and all(isinstance(x, str) for x in value):
                    safe_details.append(f"{key}: {', '.join(value)}")
            
            if safe_details:
                content_parts.append(f"Configuration: {' | '.join(safe_details)}")
        
        content = " | ".join(content_parts)
        
        # Create metadata for the document
        doc_metadata = {
            "tool_name": self.name,
            "tool_type": self.type,
            "created_at": self.created_at.isoformat(),
        }
        
        if self.capabilities:
            doc_metadata["capabilities"] = self.capabilities
        
        if self.description:
            doc_metadata["description"] = self.description
        
        if self.metadata:
            doc_metadata.update(self.metadata)
        
        return SourceDocument(
            source_type=CopilotDocumentSourceType.TOOL_REGISTRY,
            source_id=self.tool_id,
            content=content,
            metadata=doc_metadata,
        )


class ToolRegistryIndexer(BaseIndexer):
    """
    Indexes tool registry entries for Copilot RAG retrieval.
    
    Features:
    - Explicit redaction of sensitive configuration data
    - Safe metadata extraction (name, type, capabilities, descriptions)
    - Tenant isolation for tool definitions
    - Integration with existing chunking and embedding services
    
    Security:
    - Removes all keys, secrets, tokens, auth configs, connection strings
    - Pattern-based detection of sensitive field names and values
    - Only stores safe metadata for RAG retrieval
    """

    def __init__(
        self,
        db_session: AsyncSession,
        embedding_service: EmbeddingService,
        chunking_service: DocumentChunkingService,
        document_repository: CopilotDocumentRepository,
    ):
        super().__init__(
            document_repository=document_repository,
            embedding_service=embedding_service,
            chunking_service=chunking_service,
        )
        self.db_session = db_session
        self._source_type = CopilotDocumentSourceType.TOOL_REGISTRY

    @property
    def source_type(self) -> CopilotDocumentSourceType:
        """Return the source type handled by this indexer."""
        return self._source_type

    async def index_incremental(
        self,
        tenant_id: str,
        source_id: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        domain: Optional[str] = None,
        source_version: Optional[str] = None,
    ) -> IndexingResult:
        """
        Perform incremental indexing of a single tool definition.
        
        Note: This method supports single-tool indexing, but the main
        entry point is index_tools_for_tenant() for batch processing.
        """
        # For single tool indexing, we need to load the tool from database
        # This is a simplified implementation for the interface compliance
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get the specific tool
            query = select(ToolDefinition).where(
                ToolDefinition.tool_id == int(source_id),
                ToolDefinition.tenant_id == tenant_id if tenant_id else ToolDefinition.tenant_id.is_(None)
            )
            result = await self.db_session.execute(query)
            tool = result.scalar_one_or_none()
            
            if not tool:
                return self._create_indexing_result(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    start_time=start_time,
                    success=True,
                    chunks_processed=0,
                    chunks_indexed=0,
                    metadata={"message": "Tool not found"},
                )
            
            # Convert to redacted document
            tool_doc = self._convert_tool_to_doc(tool)
            
            # Index the document
            result = await self.index_tool_registry(tenant_id, [tool_doc])
            return result
            
        except Exception as e:
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=source_id,
                start_time=start_time,
                success=False,
                error_message=str(e),
            )

    async def index_full(
        self,
        tenant_id: str,
        force_reindex: bool = False,
    ) -> list[IndexingResult]:
        """
        Perform full indexing of all tool definitions for tenant.
        """
        # Full indexing delegates to index_tools_for_tenant
        result = await self.index_tools_for_tenant(tenant_id)
        return [result]

    async def index_tools_for_tenant(self, tenant_id: Optional[str]) -> IndexingResult:
        """
        Index all tool definitions for a specific tenant or global tools.
        
        Args:
            tenant_id: Tenant ID for scoping (None for global tools)
            
        Returns:
            IndexingResult with processing statistics
        """
        logger.info(f"Starting tool registry indexing for tenant: {tenant_id}")
        start_time = datetime.now(timezone.utc)

        if tenant_id is not None and not self.supports_tenant(tenant_id):
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=f"tool-registry-{tenant_id or 'global'}",
                success=False,
                error_message="Invalid tenant ID",
                start_time=start_time,
            )

        try:
            # Get tool definitions for tenant
            tools = await self._get_tools_for_tenant(tenant_id)
            
            if not tools:
                logger.info(f"No tools found for tenant {tenant_id}")
                return self._create_indexing_result(
                    tenant_id=tenant_id,
                    source_id=f"tool-registry-{tenant_id or 'global'}",
                    start_time=start_time,
                    success=True,
                    chunks_processed=0,
                    chunks_indexed=0,
                    metadata={"tools_count": 0},
                )

            # Convert to redacted document format
            tool_docs = [self._convert_tool_to_doc(tool) for tool in tools]
            
            # Index the documents
            result = await self.index_tool_registry(tenant_id, tool_docs)
            
            return result
            
        except (ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Tool registry indexing failed for tenant {tenant_id}: {str(e)}")
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=f"tool-registry-{tenant_id or 'global'}",
                start_time=start_time,
                success=False,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
            )

    async def index_tool_registry(
        self,
        tenant_id: Optional[str],
        tool_docs: List[ToolRegistryDoc],
    ) -> IndexingResult:
        """
        Index a list of tool registry documents.

        Args:
            tenant_id: Tenant ID for isolation (None for global tools)
            tool_docs: List of redacted tool docs to index

        Returns:
            IndexingResult with processing statistics
        """
        logger.info(f"Indexing {len(tool_docs)} tools for tenant {tenant_id}")
        start_time = datetime.now(timezone.utc)

        if not tool_docs:
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=f"tool-registry-batch-{tenant_id or 'global'}",
                start_time=start_time,
                success=True,
                chunks_processed=0,
                chunks_indexed=0,
                metadata={"total_tools": 0},
            )

        try:
            all_chunks = []
            processed_count = 0

            # Process each tool
            for tool_doc in tool_docs:
                try:
                    # Convert to source document
                    source_doc = tool_doc.to_source_document()

                    # Chunk the document
                    chunks = self.chunking_service.chunk_document(source_doc)

                    if not chunks:
                        logger.warning(f"No chunks generated for tool {tool_doc.tool_id} (tenant: {tenant_id})")
                        continue

                    all_chunks.extend(chunks)
                    processed_count += len(chunks)

                except (IndexingError, ValueError, TypeError, RuntimeError) as e:
                    logger.error(f"Failed to process tool {tool_doc.tool_id}: {str(e)}")
                    continue

            # Batch index all chunks
            if all_chunks:
                indexed_count = await self.document_repository.upsert_documents_batch(
                    tenant_id=tenant_id,
                    chunks=all_chunks,
                )
            else:
                indexed_count = 0

            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()

            logger.info(
                f"Tool registry indexing completed: "
                f"{processed_count} chunks processed, {indexed_count} indexed, "
                f"{processing_time:.2f}s"
            )

            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=f"tool-registry-batch-{tenant_id or 'global'}",
                start_time=start_time,
                end_time=end_time,
                success=True,
                chunks_processed=processed_count,
                chunks_indexed=indexed_count,
                metadata={
                    "total_tools": len(tool_docs),
                    "processing_time_seconds": processing_time,
                },
            )

        except (IndexingError, ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Tool registry indexing failed for tenant {tenant_id}: {str(e)}")
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=f"tool-registry-batch-{tenant_id or 'global'}",
                start_time=start_time,
                success=False,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
            )

    async def _get_tools_for_tenant(self, tenant_id: Optional[str]) -> List[ToolDefinition]:
        """Get tool definitions for tenant."""
        try:
            query = select(ToolDefinition).order_by(ToolDefinition.created_at.asc())
            
            # Apply tenant filtering
            if tenant_id is not None:
                # For specific tenant, get only their tools
                query = query.where(ToolDefinition.tenant_id == tenant_id)
            else:
                # For global indexing, get only global tools (tenant_id is NULL)
                query = query.where(ToolDefinition.tenant_id.is_(None))
            
            result = await self.db_session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to fetch tools for tenant {tenant_id}: {str(e)}")
            raise RuntimeError(f"Database query failed: {str(e)}")

    def _convert_tool_to_doc(self, tool: ToolDefinition) -> ToolRegistryDoc:
        """Convert ToolDefinition to redacted ToolRegistryDoc."""
        # Redact sensitive configuration data
        safe_config = self._redact_sensitive_config(tool.config or {})
        
        # Extract capabilities and description from config
        capabilities = self._extract_capabilities(tool.config or {})
        description = self._extract_description(tool.config or {})
        
        return ToolRegistryDoc(
            tool_id=str(tool.tool_id),
            tenant_id=tool.tenant_id,
            name=tool.name,
            type=tool.type,
            safe_config=safe_config,
            capabilities=capabilities,
            description=description,
            created_at=tool.created_at,
            metadata={
                "tool_id": tool.tool_id,
            },
        )

    def _redact_sensitive_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact sensitive information from tool configuration.
        
        Removes all keys, secrets, tokens, auth configs, connection strings
        and other sensitive data, keeping only safe metadata.
        """
        if not config:
            return {}
        
        safe_config = {}
        
        for key, value in config.items():
            # Special handling for headers - process contents, don't remove entire section
            if key.lower() == "headers" and isinstance(value, dict):
                safe_headers = {}
                for header_name, header_value in value.items():
                    if not self._is_sensitive_header(header_name):
                        if not (isinstance(header_value, str) and self._is_sensitive_value(header_value)):
                            safe_headers[header_name] = header_value
                
                if safe_headers:
                    safe_config[key] = safe_headers
                continue
            
            # Skip sensitive fields based on field name
            if self._is_sensitive_field(key):
                continue
            
            # Skip sensitive values even if field name seems safe
            if isinstance(value, str) and self._is_sensitive_value(value):
                continue
            
            # Recursively process nested dictionaries
            if isinstance(value, dict):
                safe_nested = self._redact_sensitive_config(value)
                if safe_nested:  # Only include if not empty after redaction
                    safe_config[key] = safe_nested
            # Process lists
            elif isinstance(value, list):
                safe_list = []
                for item in value:
                    if isinstance(item, dict):
                        safe_item = self._redact_sensitive_config(item)
                        if safe_item:
                            safe_list.append(safe_item)
                    elif isinstance(item, str):
                        if not self._is_sensitive_value(item):
                            safe_list.append(item)
                    else:
                        safe_list.append(item)
                
                if safe_list:
                    safe_config[key] = safe_list
            # Include safe primitive values
            elif isinstance(value, (str, int, float, bool)) and not self._is_sensitive_value(str(value)):
                safe_config[key] = value
        
        return safe_config

    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if a field name indicates sensitive data."""
        if not field_name:
            return False
        
        field_lower = field_name.lower()
        
        # Check exact matches and pattern matches
        for pattern in SENSITIVE_FIELD_PATTERNS:
            if isinstance(pattern, str):
                if pattern in field_lower:
                    return True
            else:
                # Regex pattern
                if re.match(pattern, field_lower):
                    return True
        
        return False

    def _is_sensitive_header(self, header_name: str) -> bool:
        """Check if a header name indicates sensitive data."""
        if not header_name:
            return False
        
        header_lower = header_name.lower()
        return header_lower in SENSITIVE_HEADERS

    def _is_sensitive_value(self, value: str) -> bool:
        """Check if a value looks like sensitive data (token, key, etc.)."""
        if not value or len(value) < 8:  # Very short values are probably safe
            return False
        
        # Check against sensitive value patterns
        for pattern in SENSITIVE_VALUE_PATTERNS:
            if re.match(pattern, value):
                return True
        
        return False

    def _extract_capabilities(self, config: Dict[str, Any]) -> List[str]:
        """Extract tool capabilities from configuration."""
        capabilities = []
        
        # Common capability fields
        capability_fields = [
            "capabilities", "actions", "methods", "operations", "functions",
            "supported_actions", "available_methods", "endpoints"
        ]
        
        for field in capability_fields:
            value = config.get(field)
            if isinstance(value, list):
                capabilities.extend(str(item) for item in value if item)
            elif isinstance(value, str):
                # Split on common delimiters
                parts = re.split(r'[,;|]', value)
                capabilities.extend(part.strip() for part in parts if part.strip())
        
        # Extract from endpoint/method configurations
        if "endpoints" in config and isinstance(config["endpoints"], dict):
            capabilities.extend(config["endpoints"].keys())
        
        if "methods" in config and isinstance(config["methods"], dict):
            capabilities.extend(config["methods"].keys())
        
        # Remove duplicates and return
        return list(set(capabilities))

    def _extract_description(self, config: Dict[str, Any]) -> Optional[str]:
        """Extract tool description from configuration."""
        description_fields = [
            "description", "summary", "purpose", "usage", "about", "info"
        ]
        
        for field in description_fields:
            value = config.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        
        return None

    def _create_indexing_result(
        self,
        tenant_id: Optional[str],
        source_id: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        success: bool = True,
        chunks_processed: int = 0,
        chunks_indexed: int = 0,
        error_message: Optional[str] = None,
        error_details: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> IndexingResult:
        """Create a standardized indexing result."""
        if end_time is None:
            end_time = datetime.now(timezone.utc)
            
        return IndexingResult(
            tenant_id=tenant_id,
            source_type=self.source_type,
            source_id=source_id,
            success=success,
            chunks_processed=chunks_processed,
            chunks_indexed=chunks_indexed,
            start_time=start_time,
            end_time=end_time,
            error_message=error_message,
            error_details=error_details or {},
            metadata=metadata or {},
        )

    def supports_tenant(self, tenant_id: Optional[str]) -> bool:
        """
        Check if the indexer supports a given tenant.
        
        Args:
            tenant_id: Tenant ID to check (None for global)
            
        Returns:
            True if tenant is supported
        """
        # Support all valid tenant IDs and global tools (None)
        if tenant_id is None:
            return True
        
        return validate_tenant_id(tenant_id)