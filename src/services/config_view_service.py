"""
Configuration View Service for Phase 3.

Provides viewing, listing, and diffing capabilities for:
- Domain Packs
- Tenant Policy Packs
- Playbooks

Matches specification from phase3-mvp-issues.md P3-16.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from src.domainpack.storage import DomainPackStorage
from src.models.domain_pack import DomainPack, Playbook
from src.models.tenant_policy import TenantPolicyPack
from src.tenantpack.loader import TenantPolicyRegistry

logger = logging.getLogger(__name__)


class ConfigType(str, Enum):
    """Configuration type enumeration."""

    DOMAIN_PACK = "domain_pack"
    TENANT_POLICY = "tenant_policy"
    PLAYBOOK = "playbook"


class ConfigViewService:
    """
    Service for viewing and diffing configurations.
    
    Phase 3 MVP: Simple viewing and diffing, no heavy analytics.
    """

    def __init__(
        self,
        domain_pack_storage: Optional[DomainPackStorage] = None,
        tenant_policy_registry: Optional[TenantPolicyRegistry] = None,
    ):
        """
        Initialize config view service.
        
        Args:
            domain_pack_storage: Optional DomainPackStorage instance
            tenant_policy_registry: Optional TenantPolicyRegistry instance
        """
        self.domain_pack_storage = domain_pack_storage or DomainPackStorage()
        self.tenant_policy_registry = tenant_policy_registry or TenantPolicyRegistry()

    def list_configs(
        self,
        config_type: ConfigType,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        List configurations of a given type.
        
        Args:
            config_type: Type of configuration to list
            tenant_id: Optional tenant filter
            domain: Optional domain filter
            
        Returns:
            List of configuration summaries with:
            {
                "id": str,
                "name": str,
                "version": str,
                "tenant_id": str,
                "domain": str (for domain packs),
                "timestamp": str,
            }
        """
        configs = []
        
        if config_type == ConfigType.DOMAIN_PACK:
            # List domain packs from storage
            storage_root = Path("./runtime/domainpacks")
            if not storage_root.exists():
                return configs
            
            # Iterate through tenant directories
            for tenant_dir in storage_root.iterdir():
                if not tenant_dir.is_dir():
                    continue
                
                current_tenant_id = tenant_dir.name
                
                # Filter by tenant if provided
                if tenant_id and current_tenant_id != tenant_id:
                    continue
                
                # Iterate through domain directories
                for domain_dir in tenant_dir.iterdir():
                    if not domain_dir.is_dir():
                        continue
                    
                    current_domain = domain_dir.name
                    
                    # Filter by domain if provided
                    if domain and current_domain != domain:
                        continue
                    
                    # List versions for this domain
                    versions = self.domain_pack_storage.list_versions(current_tenant_id, current_domain)
                    for version in versions:
                        pack = self.domain_pack_storage.get_pack(current_tenant_id, current_domain, version)
                        if pack:
                            # Get file timestamp
                            pack_path = storage_root / current_tenant_id / current_domain / f"{version}.json"
                            timestamp = None
                            if pack_path.exists():
                                timestamp = datetime.fromtimestamp(pack_path.stat().st_mtime).isoformat()
                            
                            configs.append({
                                "id": f"{current_tenant_id}:{current_domain}:{version}",
                                "name": pack.domain_name,
                                "version": version,
                                "tenant_id": current_tenant_id,
                                "domain": current_domain,
                                "timestamp": timestamp,
                            })
        
        elif config_type == ConfigType.TENANT_POLICY:
            # List tenant policies from registry
            tenant_ids = self.tenant_policy_registry.list_tenants()
            
            for tid in tenant_ids:
                # Filter by tenant if provided
                if tenant_id and tid != tenant_id:
                    continue
                
                policy = self.tenant_policy_registry.get(tid)
                if policy:
                    configs.append({
                        "id": f"{tid}:{policy.domain_name}",
                        "name": f"Tenant Policy for {tid}",
                        "version": "1.0.0",  # MVP: tenant policies don't have versioning yet
                        "tenant_id": tid,
                        "domain": policy.domain_name,
                        "timestamp": None,  # MVP: no timestamp tracking yet
                    })
        
        elif config_type == ConfigType.PLAYBOOK:
            # List playbooks from domain packs
            # Playbooks are embedded in domain packs, so we extract them
            storage_root = Path("./runtime/domainpacks")
            if not storage_root.exists():
                return configs
            
            for tenant_dir in storage_root.iterdir():
                if not tenant_dir.is_dir():
                    continue
                
                current_tenant_id = tenant_dir.name
                
                # Filter by tenant if provided
                if tenant_id and current_tenant_id != tenant_id:
                    continue
                
                for domain_dir in tenant_dir.iterdir():
                    if not domain_dir.is_dir():
                        continue
                    
                    current_domain = domain_dir.name
                    
                    # Filter by domain if provided
                    if domain and current_domain != domain:
                        continue
                    
                    # Get latest domain pack to extract playbooks
                    pack = self.domain_pack_storage.get_pack(current_tenant_id, current_domain)
                    if pack and pack.playbooks:
                        # Get the version from storage (packs don't have embedded version)
                        versions = self.domain_pack_storage.list_versions(current_tenant_id, current_domain)
                        pack_version = versions[-1] if versions else "1.0.0"
                        
                        for playbook in pack.playbooks:
                            configs.append({
                                "id": f"{current_tenant_id}:{current_domain}:{playbook.exception_type}",
                                "name": f"Playbook for {playbook.exception_type}",
                                "version": pack_version,
                                "tenant_id": current_tenant_id,
                                "domain": current_domain,
                                "exception_type": playbook.exception_type,
                                "timestamp": None,
                            })
        
        return configs

    def get_config_by_id(
        self,
        config_type: ConfigType,
        config_id: str,
    ) -> Optional[dict[str, Any]]:
        """
        Get a specific configuration by ID.
        
        Args:
            config_type: Type of configuration
            config_id: Configuration identifier (format depends on type)
            
        Returns:
            Configuration dictionary or None if not found
        """
        if config_type == ConfigType.DOMAIN_PACK:
            # Format: tenant_id:domain:version
            parts = config_id.split(":")
            if len(parts) != 3:
                return None
            
            tenant_id, domain, version = parts
            pack = self.domain_pack_storage.get_pack(tenant_id, domain, version)
            if pack:
                return {
                    "id": config_id,
                    "type": "domain_pack",
                    "data": pack.model_dump(),
                }
        
        elif config_type == ConfigType.TENANT_POLICY:
            # Format: tenant_id:domain
            parts = config_id.split(":")
            if len(parts) != 2:
                return None
            
            tenant_id, domain = parts
            policy = self.tenant_policy_registry.get(tenant_id)
            if policy and policy.domain_name == domain:
                return {
                    "id": config_id,
                    "type": "tenant_policy",
                    "data": policy.model_dump(),
                }
        
        elif config_type == ConfigType.PLAYBOOK:
            # Format: tenant_id:domain:exception_type
            parts = config_id.split(":")
            if len(parts) != 3:
                return None
            
            tenant_id, domain, exception_type = parts
            pack = self.domain_pack_storage.get_pack(tenant_id, domain)
            if pack:
                for playbook in pack.playbooks:
                    if playbook.exception_type == exception_type:
                        return {
                            "id": config_id,
                            "type": "playbook",
                            "data": playbook.model_dump(),
                        }
        
        return None

    def diff_configs(
        self,
        config_type: ConfigType,
        left_id: str,
        right_id: str,
    ) -> dict[str, Any]:
        """
        Diff two configurations.
        
        Args:
            config_type: Type of configuration
            left_id: Left configuration ID
            right_id: Right configuration ID
            
        Returns:
            Dictionary with structured diff:
            {
                "left": dict,
                "right": dict,
                "differences": {
                    "added": list,
                    "removed": list,
                    "modified": list,
                },
                "summary": {
                    "total_changes": int,
                    "additions": int,
                    "deletions": int,
                    "modifications": int,
                }
            }
        """
        # Get both configurations
        left_config = self.get_config_by_id(config_type, left_id)
        right_config = self.get_config_by_id(config_type, right_id)
        
        if not left_config or not right_config:
            raise ValueError(f"One or both configurations not found: left={left_id}, right={right_id}")
        
        left_data = left_config["data"]
        right_data = right_config["data"]
        
        # Perform diff based on type
        if config_type == ConfigType.DOMAIN_PACK:
            return self._diff_domain_packs(left_data, right_data)
        elif config_type == ConfigType.TENANT_POLICY:
            return self._diff_tenant_policies(left_data, right_data)
        elif config_type == ConfigType.PLAYBOOK:
            return self._diff_playbooks(left_data, right_data)
        else:
            return self._diff_generic(left_data, right_data)

    def _diff_domain_packs(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> dict[str, Any]:
        """Diff two domain packs."""
        differences = {
            "added": [],
            "removed": [],
            "modified": [],
        }
        
        # Compare top-level fields
        for key in set(left.keys()) | set(right.keys()):
            if key not in right:
                differences["removed"].append({"field": key, "left_value": left.get(key)})
            elif key not in left:
                differences["added"].append({"field": key, "right_value": right.get(key)})
            elif left.get(key) != right.get(key):
                # For complex fields, do deeper comparison
                if key in ["exception_types", "playbooks", "tools", "severity_rules"]:
                    # Compare lists/dicts
                    left_items = left.get(key, [])
                    right_items = right.get(key, [])
                    if isinstance(left_items, list) and isinstance(right_items, list):
                        # Simple list comparison for MVP
                        if len(left_items) != len(right_items):
                            differences["modified"].append({
                                "field": key,
                                "left_count": len(left_items),
                                "right_count": len(right_items),
                            })
                        else:
                            # Check for item-level changes
                            for i, (left_item, right_item) in enumerate(zip(left_items, right_items)):
                                if left_item != right_item:
                                    differences["modified"].append({
                                        "field": f"{key}[{i}]",
                                        "left_value": left_item,
                                        "right_value": right_item,
                                    })
                    else:
                        differences["modified"].append({
                            "field": key,
                            "left_value": left.get(key),
                            "right_value": right.get(key),
                        })
                else:
                    differences["modified"].append({
                        "field": key,
                        "left_value": left.get(key),
                        "right_value": right.get(key),
                    })
        
        return {
            "left": left,
            "right": right,
            "differences": differences,
            "summary": {
                "total_changes": len(differences["added"]) + len(differences["removed"]) + len(differences["modified"]),
                "additions": len(differences["added"]),
                "deletions": len(differences["removed"]),
                "modifications": len(differences["modified"]),
            },
        }

    def _diff_tenant_policies(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> dict[str, Any]:
        """Diff two tenant policies."""
        return self._diff_generic(left, right)

    def _diff_playbooks(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> dict[str, Any]:
        """Diff two playbooks."""
        return self._diff_generic(left, right)

    def _diff_generic(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> dict[str, Any]:
        """Generic diff for any dictionary."""
        differences = {
            "added": [],
            "removed": [],
            "modified": [],
        }
        
        for key in set(left.keys()) | set(right.keys()):
            if key not in right:
                differences["removed"].append({"field": key, "left_value": left.get(key)})
            elif key not in left:
                differences["added"].append({"field": key, "right_value": right.get(key)})
            elif left.get(key) != right.get(key):
                differences["modified"].append({
                    "field": key,
                    "left_value": left.get(key),
                    "right_value": right.get(key),
                })
        
        return {
            "left": left,
            "right": right,
            "differences": differences,
            "summary": {
                "total_changes": len(differences["added"]) + len(differences["removed"]) + len(differences["modified"]),
                "additions": len(differences["added"]),
                "deletions": len(differences["removed"]),
                "modifications": len(differences["modified"]),
            },
        }

    def get_config_history(
        self,
        config_type: ConfigType,
        config_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get version history for a configuration.
        
        Args:
            config_type: Type of configuration
            config_id: Configuration identifier
            
        Returns:
            List of version entries with:
            {
                "version": str,
                "timestamp": str,
                "id": str,
            }
        """
        history = []
        
        if config_type == ConfigType.DOMAIN_PACK:
            # Extract tenant and domain from ID
            parts = config_id.split(":")
            if len(parts) >= 2:
                tenant_id = parts[0]
                domain = parts[1]
                
                versions = self.domain_pack_storage.list_versions(tenant_id, domain)
                storage_root = Path("./runtime/domainpacks")
                
                for version in versions:
                    pack_path = storage_root / tenant_id / domain / f"{version}.json"
                    timestamp = None
                    if pack_path.exists():
                        timestamp = datetime.fromtimestamp(pack_path.stat().st_mtime).isoformat()
                    
                    history.append({
                        "version": version,
                        "timestamp": timestamp,
                        "id": f"{tenant_id}:{domain}:{version}",
                    })
        
        elif config_type == ConfigType.TENANT_POLICY:
            # MVP: Tenant policies don't have versioning yet
            parts = config_id.split(":")
            if len(parts) >= 2:
                tenant_id = parts[0]
                history.append({
                    "version": "1.0.0",
                    "timestamp": None,
                    "id": config_id,
                })
        
        elif config_type == ConfigType.PLAYBOOK:
            # Playbooks inherit version from domain pack
            parts = config_id.split(":")
            if len(parts) >= 2:
                tenant_id = parts[0]
                domain = parts[1]
                
                versions = self.domain_pack_storage.list_versions(tenant_id, domain)
                for version in versions:
                    history.append({
                        "version": version,
                        "timestamp": None,
                        "id": f"{config_id}:{version}",
                    })
        
        # Sort by version (most recent first for MVP)
        history.sort(key=lambda x: x.get("version", ""), reverse=True)
        
        return history


# Singleton instance
_config_view_service: Optional[ConfigViewService] = None


def get_config_view_service() -> ConfigViewService:
    """
    Get the global config view service instance.
    
    Returns:
        ConfigViewService instance
    """
    global _config_view_service
    if _config_view_service is None:
        _config_view_service = ConfigViewService()
    return _config_view_service

