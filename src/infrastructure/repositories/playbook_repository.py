"""
Playbook repository for playbook management.

Phase 6 P6-13: PlaybookRepository with CRUD operations and filtering.
Phase 7 P7-6: Enhanced with candidate playbook queries and playbook-with-steps retrieval.

Note: Playbooks are tenant-specific, so this repository enforces
strict tenant isolation on all operations.
"""

import logging
from typing import Optional, Tuple

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import Playbook, PlaybookStep
from src.repository.base import AbstractBaseRepository
from src.repository.dto import PlaybookCreateDTO, PlaybookFilter

logger = logging.getLogger(__name__)


class PlaybookRepository(AbstractBaseRepository[Playbook]):
    """
    Repository for playbook management.
    
    Provides:
    - Get playbook by ID with tenant isolation
    - List playbooks with filtering
    - Create new playbook
    - Tenant isolation enforcement
    
    All operations enforce strict tenant isolation - queries are always
    filtered by tenant_id to ensure data separation.
    """

    async def get_playbook(
        self,
        playbook_id: int,
        tenant_id: str,
    ) -> Optional[Playbook]:
        """
        Get a playbook by ID with tenant isolation.
        
        Args:
            playbook_id: Playbook identifier (primary key)
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            Playbook instance or None if not found or tenant mismatch
            
        Raises:
            ValueError: If tenant_id is None/empty, or playbook_id < 1
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if playbook_id < 1:
            raise ValueError("playbook_id must be >= 1")
        
        query = select(Playbook).where(
            Playbook.playbook_id == playbook_id,
            Playbook.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_playbook_by_name(
        self,
        tenant_id: str,
        name: str,
    ) -> Optional[Playbook]:
        """
        Get a playbook by exact name with tenant isolation.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            name: Exact playbook name to match
            
        Returns:
            Playbook instance or None if not found
            
        Raises:
            ValueError: If tenant_id or name is None/empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if not name or not name.strip():
            raise ValueError("name is required")
        
        query = select(Playbook).where(
            Playbook.tenant_id == tenant_id,
            Playbook.name == name,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_playbooks(
        self,
        tenant_id: str,
        filters: Optional[PlaybookFilter] = None,
    ) -> list[Playbook]:
        """
        List playbooks for a tenant with optional filtering.
        
        Results are ordered by created_at (descending, newest first).
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            filters: Optional PlaybookFilter for filtering playbooks
            
        Returns:
            List of Playbook instances for the tenant
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(Playbook).where(Playbook.tenant_id == tenant_id)
        
        # Apply filters if provided
        if filters:
            conditions = []
            
            # Filter by name (partial match, case-insensitive)
            if filters.name:
                conditions.append(Playbook.name.ilike(f"%{filters.name}%"))
            
            # Filter by version
            if filters.version is not None:
                conditions.append(Playbook.version == filters.version)
            
            # Filter by created_from
            if filters.created_from:
                conditions.append(Playbook.created_at >= filters.created_from)
            
            # Filter by created_to
            if filters.created_to:
                conditions.append(Playbook.created_at <= filters.created_to)
            
            # Apply all conditions
            if conditions:
                query = query.where(and_(*conditions))
        
        # Order by created_at descending (newest first)
        query = query.order_by(desc(Playbook.created_at))
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_candidate_playbooks(
        self,
        tenant_id: str,
        domain: Optional[str] = None,
        exception_type: Optional[str] = None,
        severity: Optional[str] = None,
        sla_minutes_remaining: Optional[int] = None,
        policy_tags: Optional[list[str]] = None,
    ) -> list[Playbook]:
        """
        Get candidate playbooks for matching with filtering.
        
        Phase 7 P7-6: Enhanced query method that filters playbooks based on conditions
        stored in the JSONB conditions column. Filters by domain, exception_type, severity,
        SLA window, and policy_tags.
        
        Results are ordered by priority (descending, if present in conditions), then by
        created_at (descending, newest first).
        
        Indexing notes:
        - tenant_id is indexed (see Playbook model) for efficient tenant isolation
        - domain, exception_type, severity are stored in JSONB conditions column
          (GIN indexes on conditions JSONB can be added for production optimization)
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            domain: Optional domain filter (matches conditions.match.domain or conditions.domain)
            exception_type: Optional exception type filter (matches conditions.match.exception_type or conditions.exception_type)
            severity: Optional severity filter (matches conditions.match.severity/severity_in or conditions.severity/severity_in)
            sla_minutes_remaining: Optional SLA minutes remaining (for conditions.match.sla_minutes_remaining_lt)
            policy_tags: Optional list of policy tags (subset match against conditions.match.policy_tags or conditions.policy_tags)
            
        Returns:
            List of Playbook instances matching the filters, ordered by priority desc, then created_at desc
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Start with base query - always filter by tenant_id
        query = select(Playbook).where(Playbook.tenant_id == tenant_id)
        
        # For MVP, we load all playbooks for the tenant and filter in Python
        # This is simpler and more reliable than complex JSONB queries
        # Future optimization: Add database indexes and use JSONB operators for SQL-level filtering
        query = query.order_by(desc(Playbook.created_at))
        
        result = await self.session.execute(query)
        all_playbooks = list(result.scalars().all())
        
        # Filter playbooks based on conditions in Python
        filtered_playbooks = []
        for playbook in all_playbooks:
            # Handle JSONB conditions - may be dict or JSON string (SQLite compatibility)
            conditions_raw = playbook.conditions or {}
            if isinstance(conditions_raw, str):
                import json
                try:
                    conditions = json.loads(conditions_raw)
                except (json.JSONDecodeError, TypeError):
                    conditions = {}
            else:
                conditions = conditions_raw
            match_conditions = conditions.get("match", conditions) if isinstance(conditions, dict) else {}
            
            # Filter by domain
            if domain:
                playbook_domain = match_conditions.get("domain") or conditions.get("domain")
                if not playbook_domain or playbook_domain.lower() != domain.lower():
                    continue
            
            # Filter by exception_type
            if exception_type:
                playbook_exc_type = match_conditions.get("exception_type") or conditions.get("exception_type")
                if not playbook_exc_type:
                    continue
                # Basic substring match (exact/pattern matching done by condition_engine)
                if exception_type.lower() not in playbook_exc_type.lower():
                    continue
            
            # Filter by severity
            if severity:
                severity_lower = severity.lower()
                # Check severity_in array or single severity
                severity_in = match_conditions.get("severity_in") or conditions.get("severity_in")
                playbook_severity = match_conditions.get("severity") or conditions.get("severity")
                
                severity_matches = False
                if severity_in and isinstance(severity_in, list):
                    severity_matches = severity_lower in [s.lower() for s in severity_in if isinstance(s, str)]
                elif playbook_severity:
                    severity_matches = playbook_severity.lower() == severity_lower
                
                if not severity_matches:
                    continue
            
            # Filter by SLA window (only include if playbook has sla_minutes_remaining_lt condition)
            if sla_minutes_remaining is not None:
                has_sla_condition = (
                    "sla_minutes_remaining_lt" in match_conditions or
                    "sla_minutes_remaining_lt" in conditions
                )
                if not has_sla_condition:
                    continue
            
            # Filter by policy_tags (only include if playbook has policy_tags condition)
            if policy_tags and len(policy_tags) > 0:
                has_policy_tags = (
                    "policy_tags" in match_conditions or
                    "policy_tags" in conditions
                )
                if not has_policy_tags:
                    continue
            
            filtered_playbooks.append(playbook)
        
        # Sort by priority (descending, if present), then by created_at (descending)
        def get_priority(playbook: Playbook) -> int:
            """Extract priority from playbook conditions."""
            conditions_raw = playbook.conditions or {}
            if isinstance(conditions_raw, str):
                import json
                try:
                    conditions = json.loads(conditions_raw)
                except (json.JSONDecodeError, TypeError):
                    conditions = {}
            else:
                conditions = conditions_raw
            match_conditions = conditions.get("match", conditions) if isinstance(conditions, dict) else {}
            return match_conditions.get("priority", 0) if isinstance(match_conditions, dict) else 0
        
        filtered_playbooks.sort(key=lambda p: (get_priority(p), p.created_at), reverse=True)
        
        logger.debug(
            f"Found {len(filtered_playbooks)} candidate playbooks for tenant {tenant_id} "
            f"(filters: domain={domain}, exception_type={exception_type}, severity={severity}, "
            f"sla_minutes_remaining={sla_minutes_remaining}, policy_tags={policy_tags})"
        )
        
        return filtered_playbooks

    async def create_playbook(
        self,
        tenant_id: str,
        playbook_data: PlaybookCreateDTO,
    ) -> Playbook:
        """
        Create a new playbook.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            playbook_data: PlaybookCreateDTO with playbook details
            
        Returns:
            Created Playbook instance
            
        Raises:
            ValueError: If tenant_id is None/empty, or playbook_data is invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Create new playbook
        playbook = Playbook(
            tenant_id=tenant_id,
            name=playbook_data.name,
            version=playbook_data.version,
            conditions=playbook_data.conditions,
        )
        
        self.session.add(playbook)
        await self.session.flush()
        await self.session.refresh(playbook)
        
        logger.info(f"Created playbook: playbook_id={playbook.playbook_id}, tenant_id={tenant_id}, name={playbook.name}")
        return playbook

    # AbstractBaseRepository implementations
    # Note: These methods enforce tenant isolation

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[Playbook]:
        """
        Get playbook by ID with tenant isolation.
        
        Args:
            id: Playbook database ID (as string)
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            Playbook instance or None if not found or tenant mismatch
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        try:
            playbook_id = int(id)
        except (ValueError, TypeError):
            return None
        
        # Enforce tenant isolation - must match both id and tenant_id
        query = select(Playbook).where(
            Playbook.playbook_id == playbook_id,
            Playbook.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ):
        """
        List playbooks for a tenant with pagination and filtering.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (converted to PlaybookFilter)
            
        Returns:
            PaginatedResult with playbooks
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        from src.repository.base import PaginatedResult
        
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Convert filters to PlaybookFilter if provided
        playbook_filter = None
        if filters:
            playbook_filter = PlaybookFilter(**filters)
        
        # Get all playbooks (with optional filters)
        all_playbooks = await self.list_playbooks(tenant_id, filters=playbook_filter)
        
        # Apply pagination manually
        total = len(all_playbooks)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_playbooks = all_playbooks[start_idx:end_idx]
        
        return PaginatedResult(
            items=paginated_playbooks,
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def get_playbook_with_steps(
        self,
        playbook_id: int,
        tenant_id: str,
    ) -> Tuple[Playbook, list[PlaybookStep]]:
        """
        Get a playbook with its ordered steps.
        
        Phase 7 P7-6: Retrieves a playbook and all its steps in a single query,
        with steps ordered by step_order (ascending).
        
        Args:
            playbook_id: Playbook identifier
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            Tuple of (Playbook, list[PlaybookStep]) where steps are ordered by step_order ascending
            
        Raises:
            ValueError: If tenant_id is None/empty, or playbook_id < 1
            ValueError: If playbook not found or tenant mismatch
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if playbook_id < 1:
            raise ValueError("playbook_id must be >= 1")
        
        # Get playbook with tenant isolation
        playbook = await self.get_playbook(playbook_id, tenant_id)
        if not playbook:
            raise ValueError(
                f"Playbook {playbook_id} not found for tenant {tenant_id}"
            )
        
        # Get steps ordered by step_order (ascending)
        steps_query = (
            select(PlaybookStep)
            .where(
                PlaybookStep.playbook_id == playbook_id,
            )
            .order_by(PlaybookStep.step_order.asc())
        )
        steps_result = await self.session.execute(steps_query)
        steps = list(steps_result.scalars().all())
        
        logger.debug(
            f"Retrieved playbook {playbook_id} with {len(steps)} steps for tenant {tenant_id}"
        )
        
        return (playbook, steps)


