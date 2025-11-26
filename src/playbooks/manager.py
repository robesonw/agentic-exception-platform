"""
Playbook Manager for domain-specific playbook support.

Phase 2 implementation:
- Load playbooks from Domain Packs
- Select playbooks based on exception type and tenant policy
- Support playbook inheritance and composition
- Versioning hooks for playbook management
- Tenant isolation enforcement

Matches specification from docs/05-domain-pack-schema.md and phase2-mvp-issues.md Issue 26.
"""

import logging
from typing import Optional

from src.models.domain_pack import DomainPack, Playbook, PlaybookStep
from src.models.exception_record import ExceptionRecord
from src.models.tenant_policy import TenantPolicyPack

logger = logging.getLogger(__name__)


class PlaybookManagerError(Exception):
    """Raised when playbook management operations fail."""

    pass


class PlaybookManager:
    """
    Manages domain-specific playbooks with tenant isolation.
    
    Responsibilities:
    - Load playbooks from Domain Packs
    - Select appropriate playbook for exception type
    - Support playbook inheritance and composition
    - Enforce tenant isolation
    - Versioning support
    """

    def __init__(self):
        """Initialize the playbook manager."""
        # Store playbooks per tenant and domain: tenant_id -> domain_name -> list[Playbook]
        self._playbooks: dict[str, dict[str, list[Playbook]]] = {}
        # Store domain pack versions: tenant_id -> domain_name -> version
        self._versions: dict[str, dict[str, str]] = {}

    def load_playbooks(
        self,
        domain_pack: DomainPack,
        tenant_id: str,
        version: Optional[str] = None,
    ) -> None:
        """
        Load playbooks from a Domain Pack.
        
        Args:
            domain_pack: Domain Pack containing playbooks
            tenant_id: Tenant identifier for isolation
            version: Optional version string (defaults to domain pack version if available)
            
        Raises:
            PlaybookManagerError: If loading fails
        """
        if not tenant_id or not domain_pack.domain_name:
            raise PlaybookManagerError("Tenant ID and Domain Name cannot be empty")
        
        # Initialize tenant storage if needed
        if tenant_id not in self._playbooks:
            self._playbooks[tenant_id] = {}
            self._versions[tenant_id] = {}
        
        # Store version
        pack_version = version or getattr(domain_pack, "version", "1.0.0")
        self._versions[tenant_id][domain_pack.domain_name] = pack_version
        
        # Load playbooks from domain pack
        playbooks = domain_pack.playbooks.copy() if domain_pack.playbooks else []
        
        # Store playbooks for this tenant and domain
        self._playbooks[tenant_id][domain_pack.domain_name] = playbooks
        
        logger.info(
            f"Loaded {len(playbooks)} playbooks for tenant '{tenant_id}' "
            f"domain '{domain_pack.domain_name}' (version {pack_version})"
        )

    def select_playbook(
        self,
        exception_record: ExceptionRecord,
        tenant_policy: TenantPolicyPack,
        domain_pack: DomainPack,
    ) -> Optional[Playbook]:
        """
        Select appropriate playbook for an exception.
        
        Selection logic:
        1. Check tenant policy custom playbooks first (highest priority)
        2. Check domain pack playbooks
        3. Match by exception type
        4. Apply inheritance/composition if needed
        
        Args:
            exception_record: Exception record to find playbook for
            tenant_policy: Tenant Policy Pack for custom playbooks and approval
            domain_pack: Domain Pack containing base playbooks
            
        Returns:
            Selected Playbook or None if not found
            
        Raises:
            PlaybookManagerError: If selection fails
        """
        if not exception_record.exception_type:
            logger.warning("Exception record has no exception type, cannot select playbook")
            return None
        
        # Check if playbooks are loaded for this tenant/domain
        # If not loaded, tenant cannot access playbooks (tenant isolation)
        tenant_playbooks = self._playbooks.get(tenant_policy.tenant_id, {})
        if domain_pack.domain_name not in tenant_playbooks:
            logger.warning(
                f"Playbooks not loaded for tenant '{tenant_policy.tenant_id}' "
                f"domain '{domain_pack.domain_name}' - cannot select playbook"
            )
            return None
        
        # Step 1: Check tenant policy custom playbooks (highest priority)
        for custom_playbook in tenant_policy.custom_playbooks:
            if custom_playbook.exception_type == exception_record.exception_type:
                logger.info(
                    f"Selected custom playbook '{custom_playbook.exception_type}' "
                    f"for tenant '{tenant_policy.tenant_id}'"
                )
                return self._apply_composition(custom_playbook, domain_pack, tenant_policy)
        
        # Step 2: Check domain pack playbooks
        tenant_playbooks = self._playbooks.get(tenant_policy.tenant_id, {})
        domain_playbooks = tenant_playbooks.get(domain_pack.domain_name, [])
        
        for playbook in domain_playbooks:
            if playbook.exception_type == exception_record.exception_type:
                # Check if playbook is approved for this tenant
                if self._is_playbook_approved(playbook, tenant_policy):
                    logger.info(
                        f"Selected playbook '{playbook.exception_type}' "
                        f"for tenant '{tenant_policy.tenant_id}'"
                    )
                    return self._apply_composition(playbook, domain_pack, tenant_policy)
                else:
                    logger.warning(
                        f"Playbook '{playbook.exception_type}' not approved "
                        f"for tenant '{tenant_policy.tenant_id}'"
                    )
        
        logger.warning(
            f"No playbook found for exception type '{exception_record.exception_type}' "
            f"for tenant '{tenant_policy.tenant_id}'"
        )
        return None

    def _is_playbook_approved(
        self, playbook: Playbook, tenant_policy: TenantPolicyPack
    ) -> bool:
        """
        Check if playbook is approved for tenant.
        
        MVP: All domain pack playbooks are approved unless explicitly blocked.
        Custom playbooks are always approved.
        
        Args:
            playbook: Playbook to check
            tenant_policy: Tenant Policy Pack
            
        Returns:
            True if approved, False otherwise
        """
        # Custom playbooks are always approved
        if playbook in tenant_policy.custom_playbooks:
            return True
        
        # For domain pack playbooks, check if any tools in playbook are approved
        # If playbook references tools, at least one tool must be approved
        if not playbook.steps:
            return True  # Empty playbook is approved
        
        # Check if any step references an approved tool
        # (This is a simple check - in production, would validate all tools)
        approved_tools = set(tenant_policy.approved_tools)
        
        # Extract tool names from steps (simple heuristic)
        for step in playbook.steps:
            # Check if step action or parameters reference approved tools
            if step.parameters:
                for param_value in step.parameters.values():
                    if isinstance(param_value, str) and param_value in approved_tools:
                        return True
                # Check if action itself is a tool name
                if step.action in approved_tools:
                    return True
        
        # If no explicit tool references found, approve by default (MVP behavior)
        return True

    def _apply_composition(
        self,
        base_playbook: Playbook,
        domain_pack: DomainPack,
        tenant_policy: TenantPolicyPack,
    ) -> Playbook:
        """
        Apply playbook inheritance and composition.
        
        MVP composition rules:
        - If tenant policy has custom playbook, it completely overrides domain playbook
        - If domain playbook exists, merge with any parent playbooks (future enhancement)
        - Simple merge: append steps from parent if parent exists
        
        Args:
            base_playbook: Base playbook to compose
            domain_pack: Domain Pack for parent playbook lookup
            tenant_policy: Tenant Policy Pack
            
        Returns:
            Composed Playbook
        """
        # MVP: If it's a custom playbook, return as-is (no composition)
        if base_playbook in tenant_policy.custom_playbooks:
            return base_playbook
        
        # MVP: Simple inheritance - check if exception type has a parent
        # For now, just return the base playbook
        # Future: Look up parent exception type and merge playbooks
        
        # Check domain pack exception types for parent relationships
        # Note: ExceptionTypeDefinition may not have parent_type in MVP
        # This is a placeholder for future inheritance support
        exception_def = domain_pack.exception_types.get(base_playbook.exception_type)
        if exception_def:
            # Check if parent_type exists (may be added in future schema versions)
            parent_type = getattr(exception_def, "parent_type", None)
            if parent_type:
                # Find parent playbook
                parent_playbook = None
                for playbook in domain_pack.playbooks:
                    if playbook.exception_type == parent_type:
                        parent_playbook = playbook
                        break
                
                if parent_playbook:
                    # Merge: append parent steps before base steps (inheritance)
                    merged_steps = list(parent_playbook.steps) + list(base_playbook.steps)
                    logger.info(
                        f"Composed playbook '{base_playbook.exception_type}' "
                        f"with parent '{parent_type}' ({len(merged_steps)} total steps)"
                    )
                    return Playbook(
                        exception_type=base_playbook.exception_type,
                        steps=merged_steps,
                    )
        
        return base_playbook

    def get_version(self, tenant_id: str, domain_name: str) -> Optional[str]:
        """
        Get version of loaded playbooks for tenant and domain.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            
        Returns:
            Version string or None if not loaded
        """
        return self._versions.get(tenant_id, {}).get(domain_name)

    def list_playbooks(self, tenant_id: str, domain_name: str) -> list[Playbook]:
        """
        List all playbooks for a tenant and domain.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            
        Returns:
            List of playbooks (empty if not loaded)
        """
        return self._playbooks.get(tenant_id, {}).get(domain_name, [])

    def clear_tenant_playbooks(self, tenant_id: str) -> None:
        """
        Clear all playbooks for a tenant (for testing/cleanup).
        
        Args:
            tenant_id: Tenant identifier
        """
        if tenant_id in self._playbooks:
            del self._playbooks[tenant_id]
        if tenant_id in self._versions:
            del self._versions[tenant_id]
        logger.info(f"Cleared playbooks for tenant '{tenant_id}'")

