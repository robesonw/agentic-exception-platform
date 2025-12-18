"""
PII Redaction Metadata Repository for Phase 9.

Provides CRUD operations for PII redaction metadata.

Phase 9 P9-24: PII redaction metadata storage.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import PIIRedactionMetadata
from src.repository.base import BaseRepository

logger = logging.getLogger(__name__)


class PIIRedactionRepository(BaseRepository):
    """
    Repository for managing PII redaction metadata.
    
    Provides methods to store and retrieve redaction metadata for exceptions.
    Ensures tenant isolation for all operations.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.model = PIIRedactionMetadata
    
    async def create_redaction_metadata(
        self,
        exception_id: str,
        tenant_id: str,
        redacted_fields: list[str],
        redaction_count: int,
        redaction_placeholder: str = "[REDACTED]",
    ) -> PIIRedactionMetadata:
        """
        Create PII redaction metadata for an exception.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            redacted_fields: List of field paths that were redacted
            redaction_count: Number of fields redacted
            redaction_placeholder: Placeholder used for redacted values
            
        Returns:
            Created PIIRedactionMetadata instance
            
        Raises:
            ValueError: If required fields are missing
        """
        if not exception_id or not exception_id.strip():
            raise ValueError("exception_id is required")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        metadata = PIIRedactionMetadata(
            exception_id=exception_id,
            tenant_id=tenant_id,
            redacted_fields=redacted_fields,
            redaction_count=redaction_count,
            redaction_placeholder=redaction_placeholder,
        )
        
        self.session.add(metadata)
        await self.session.flush()
        
        logger.info(
            f"Created PII redaction metadata for exception {exception_id}: "
            f"{redaction_count} fields redacted"
        )
        
        return metadata
    
    async def get_redaction_metadata(
        self,
        exception_id: str,
        tenant_id: str,
    ) -> Optional[PIIRedactionMetadata]:
        """
        Get PII redaction metadata for an exception.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier (for isolation)
            
        Returns:
            PIIRedactionMetadata instance or None if not found
            
        Raises:
            ValueError: If tenant_id or exception_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if not exception_id or not exception_id.strip():
            raise ValueError("exception_id is required")
        
        query = select(PIIRedactionMetadata).where(
            PIIRedactionMetadata.exception_id == exception_id,
            PIIRedactionMetadata.tenant_id == tenant_id,
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update_redaction_metadata(
        self,
        exception_id: str,
        tenant_id: str,
        redacted_fields: list[str],
        redaction_count: int,
        redaction_placeholder: str = "[REDACTED]",
    ) -> Optional[PIIRedactionMetadata]:
        """
        Update PII redaction metadata for an exception.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            redacted_fields: List of field paths that were redacted
            redaction_count: Number of fields redacted
            redaction_placeholder: Placeholder used for redacted values
            
        Returns:
            Updated PIIRedactionMetadata instance or None if not found
            
        Raises:
            ValueError: If required fields are missing
        """
        metadata = await self.get_redaction_metadata(exception_id, tenant_id)
        
        if not metadata:
            return None
        
        metadata.redacted_fields = redacted_fields
        metadata.redaction_count = redaction_count
        metadata.redaction_placeholder = redaction_placeholder
        
        await self.session.flush()
        
        logger.info(
            f"Updated PII redaction metadata for exception {exception_id}: "
            f"{redaction_count} fields redacted"
        )
        
        return metadata



