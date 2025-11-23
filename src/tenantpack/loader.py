"""
Tenant Policy Pack loader and validator with domain pack validation.
Matches specification from docs/03-data-models-apis.md
"""

import json
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.models.domain_pack import DomainPack
from src.models.tenant_policy import TenantPolicyPack


class TenantPolicyValidationError(Exception):
    """Raised when Tenant Policy Pack validation fails."""

    pass


def load_tenant_policy(path: str) -> TenantPolicyPack:
    """
    Load a Tenant Policy Pack from a JSON file path.
    
    Args:
        path: Path to JSON file containing Tenant Policy Pack
        
    Returns:
        Validated TenantPolicyPack instance
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If JSON is invalid
        TenantPolicyValidationError: If validation fails
        ValidationError: If Pydantic validation fails
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Tenant Policy Pack file not found: {path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in Tenant Policy Pack file: {e.msg}", e.doc, e.pos)
    
    try:
        policy = TenantPolicyPack.model_validate(data)
    except ValidationError as e:
        raise TenantPolicyValidationError(f"Tenant Policy Pack schema validation failed: {e}") from e
    
    return policy


def validate_tenant_policy(policy: TenantPolicyPack, domain_pack: DomainPack) -> None:
    """
    Validate Tenant Policy Pack against Domain Pack.
    
    Validation rules:
    1. approvedTools must reference tools that exist in domain pack
    2. customPlaybooks must reference valid exception types from domain pack
    3. customGuardrails must align with domain guardrails structure
    4. customSeverityOverrides must reference valid exception types
    
    Args:
        policy: TenantPolicyPack instance to validate
        domain_pack: DomainPack instance to validate against
        
    Raises:
        TenantPolicyValidationError: If validation fails
    """
    errors: list[str] = []
    
    # Verify domain name matches
    if policy.domain_name != domain_pack.domain_name:
        errors.append(
            f"Tenant Policy Pack domain name '{policy.domain_name}' "
            f"does not match Domain Pack domain name '{domain_pack.domain_name}'"
        )
    
    # Rule 1: approvedTools must reference tools that exist in domain pack
    valid_tool_names = set(domain_pack.tools.keys())
    invalid_tools = [tool for tool in policy.approved_tools if tool not in valid_tool_names]
    if invalid_tools:
        errors.append(
            f"Approved tools {invalid_tools} do not exist in Domain Pack. "
            f"Valid tools: {sorted(valid_tool_names)}"
        )
    
    # Rule 2: customPlaybooks must reference valid exception types
    valid_exception_types = set(domain_pack.exception_types.keys())
    for playbook in policy.custom_playbooks:
        if playbook.exception_type not in valid_exception_types:
            errors.append(
                f"Custom playbook references invalid exception type '{playbook.exception_type}'. "
                f"Valid types: {sorted(valid_exception_types)}"
            )
        
        # Also validate tools in custom playbooks
        for step in playbook.steps:
            tool_name = _extract_tool_name_from_playbook_step(step)
            if tool_name and tool_name not in valid_tool_names:
                errors.append(
                    f"Custom playbook for '{playbook.exception_type}' references tool '{tool_name}' "
                    f"which is not defined in Domain Pack. Valid tools: {sorted(valid_tool_names)}"
                )
    
    # Rule 3: customSeverityOverrides must reference valid exception types
    invalid_exception_types = [
        override.exception_type
        for override in policy.custom_severity_overrides
        if override.exception_type not in valid_exception_types
    ]
    if invalid_exception_types:
        errors.append(
            f"Severity overrides reference invalid exception types: {invalid_exception_types}. "
            f"Valid types: {sorted(valid_exception_types)}"
        )
    
    # Rule 4: customGuardrails validation (structure alignment)
    if policy.custom_guardrails:
        # Validate that custom guardrails don't conflict with domain guardrails
        # Custom guardrails should be more restrictive, not less
        domain_guardrails = domain_pack.guardrails
        
        # Check if custom allow lists include tools not in domain allow lists
        if policy.custom_guardrails.allow_lists:
            domain_allowed = set(domain_guardrails.allow_lists)
            custom_allowed = set(policy.custom_guardrails.allow_lists)
            not_in_domain = custom_allowed - domain_allowed
            if not_in_domain:
                # This is a warning, not an error - custom can be more restrictive
                # But we should validate that these are valid tools
                invalid_custom_allowed = not_in_domain - valid_tool_names
                if invalid_custom_allowed:
                    errors.append(
                        f"Custom guardrails allow lists include invalid tools: {sorted(invalid_custom_allowed)}. "
                        f"Valid tools: {sorted(valid_tool_names)}"
                    )
        
        # Check if custom block lists include tools that are in domain allow lists
        if policy.custom_guardrails.block_lists:
            domain_allowed = set(domain_guardrails.allow_lists)
            custom_blocked = set(policy.custom_guardrails.block_lists)
            blocked_but_allowed = custom_blocked & domain_allowed
            if blocked_but_allowed:
                errors.append(
                    f"Custom guardrails block lists conflict with domain allow lists: {sorted(blocked_but_allowed)}"
                )
    
    if errors:
        error_msg = "Tenant Policy Pack validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise TenantPolicyValidationError(error_msg)


def _extract_tool_name_from_playbook_step(step) -> Optional[str]:
    """
    Extract tool name from playbook step.
    
    Similar to domain pack loader, extracts tool references from step actions.
    
    Args:
        step: PlaybookStep to analyze
        
    Returns:
        Tool name if found, None otherwise
    """
    action = step.action.lower()
    
    # Check if action directly references a tool
    if "tool" in action or "invoke" in action or "call" in action:
        import re
        # Look for patterns like invokeTool('name') or toolName('name')
        match = re.search(r"['\"]([^'\"]+)['\"]", step.action)
        if match:
            return match.group(1)
    
    # Check parameters for tool references
    if step.parameters:
        tool_keys = ["tool", "toolName", "tool_name", "action", "method"]
        for key in tool_keys:
            if key in step.parameters and isinstance(step.parameters[key], str):
                return step.parameters[key]
    
    # If action looks like a direct tool name (simple identifier)
    if step.action and "(" not in step.action and " " not in step.action:
        return step.action
    
    return None


class TenantPolicyRegistry:
    """
    In-memory registry for Tenant Policy Packs by tenant ID.
    Supports loading and retrieving Tenant Policy Packs.
    """

    def __init__(self):
        """Initialize the registry."""
        # Key: tenant_id -> TenantPolicyPack
        self._policies: dict[str, TenantPolicyPack] = {}

    def register(self, policy: TenantPolicyPack, domain_pack: DomainPack) -> None:
        """
        Register a Tenant Policy Pack in the registry.
        
        Args:
            policy: TenantPolicyPack instance to register
            domain_pack: DomainPack instance to validate against
            
        Raises:
            TenantPolicyValidationError: If policy validation fails
        """
        # Validate before registering
        validate_tenant_policy(policy, domain_pack)
        
        self._policies[policy.tenant_id] = policy

    def get(self, tenant_id: str) -> Optional[TenantPolicyPack]:
        """
        Get a Tenant Policy Pack by tenant ID.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            TenantPolicyPack instance or None if not found
        """
        return self._policies.get(tenant_id)

    def list_tenants(self) -> list[str]:
        """
        List all registered tenant IDs.
        
        Returns:
            List of tenant IDs
        """
        return sorted(self._policies.keys())

    def clear(self) -> None:
        """Clear all registered policies."""
        self._policies.clear()

    def load_from_file(self, path: str, domain_pack: DomainPack) -> TenantPolicyPack:
        """
        Load a Tenant Policy Pack from file and register it.
        
        Args:
            path: Path to JSON file
            domain_pack: DomainPack instance to validate against
            
        Returns:
            Loaded and registered TenantPolicyPack instance
        """
        policy = load_tenant_policy(path)
        self.register(policy, domain_pack)
        return policy


# Backward compatibility: Keep TenantPackLoader class
class TenantPackLoader:
    """
    Legacy loader class for backward compatibility.
    Use TenantPolicyRegistry for new code.
    """

    def __init__(self):
        """Initialize the loader."""
        self._registry = TenantPolicyRegistry()

    def load(self, pack_data: dict) -> TenantPolicyPack:
        """
        Load a Tenant Policy Pack from dictionary.
        
        Args:
            pack_data: Dictionary containing Tenant Policy Pack data
            
        Returns:
            Validated TenantPolicyPack instance
        """
        try:
            policy = TenantPolicyPack.model_validate(pack_data)
        except ValidationError as e:
            raise TenantPolicyValidationError(f"Tenant Policy Pack schema validation failed: {e}") from e
        
        return policy

    def get(self, tenant_id: str) -> Optional[TenantPolicyPack]:
        """
        Get a loaded Tenant Policy Pack by tenant ID.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            TenantPolicyPack instance or None if not found
        """
        return self._registry.get(tenant_id)

    def clear(self) -> None:
        """Clear all loaded packs."""
        self._registry.clear()
