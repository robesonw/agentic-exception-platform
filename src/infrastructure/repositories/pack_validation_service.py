"""
Pack Validation Service (P12-9).

Validates domain packs and tenant packs for schema correctness, required fields,
unsupported keys, and cross-references.

Reference: docs/phase12-onboarding-packs-mvp.md Section 5.2
"""

import logging
from dataclasses import dataclass
from typing import Any

from src.models.domain_pack import DomainPack
from src.models.tenant_policy import TenantPolicyPack

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of pack validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]


class PackValidationService:
    """
    Service for validating domain packs and tenant packs.
    
    Validates:
    - Schema correctness (required fields, types)
    - Required fields are present
    - Unsupported keys are not present
    - Cross-reference checks (playbooks/tools exist)
    """

    def validate_domain_pack(self, pack_data: dict[str, Any]) -> ValidationResult:
        """
        Validate a domain pack.
        
        Args:
            pack_data: Domain pack as dictionary
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []
        
        # Try to parse as DomainPack to validate schema
        try:
            pack = DomainPack.model_validate(pack_data)
        except Exception as e:
            errors.append(f"Schema validation failed: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Check required fields
        if not pack.domain_name:
            errors.append("domainName is required")
        if not pack.exception_types:
            errors.append("exceptionTypes must contain at least one exception type")
        
        # Check for unsupported keys (Pydantic will reject extra keys if extra="forbid")
        # But we can add explicit checks here if needed
        
        # Cross-reference checks: playbooks reference valid exception types
        valid_exception_types = set(pack.exception_types.keys())
        for playbook in pack.playbooks:
            if playbook.exception_type not in valid_exception_types:
                errors.append(
                    f"Playbook references invalid exception type '{playbook.exception_type}'. "
                    f"Valid types: {sorted(valid_exception_types)}"
                )
            
            # Check playbook steps reference valid tools
            valid_tool_names = set(pack.tools.keys())
            for step in playbook.steps:
                tool_name = self._extract_tool_name_from_step(step)
                if tool_name and tool_name not in valid_tool_names:
                    errors.append(
                        f"Playbook '{playbook.exception_type}' references tool '{tool_name}' "
                        f"which is not defined in tools. Valid tools: {sorted(valid_tool_names)}"
                    )
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def validate_tenant_pack(
        self, pack_data: dict[str, Any], domain_pack: DomainPack | None = None
    ) -> ValidationResult:
        """
        Validate a tenant pack.
        
        Args:
            pack_data: Tenant pack as dictionary
            domain_pack: Optional domain pack for cross-reference validation
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []
        
        # Try to parse as TenantPolicyPack to validate schema
        try:
            pack = TenantPolicyPack.model_validate(pack_data)
        except Exception as e:
            errors.append(f"Schema validation failed: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Check required fields
        if not pack.tenant_id:
            errors.append("tenantId is required")
        if not pack.domain_name:
            errors.append("domainName is required")
        
        # Cross-reference checks if domain_pack is provided
        if domain_pack:
            # Verify domain name matches
            if pack.domain_name != domain_pack.domain_name:
                errors.append(
                    f"Tenant pack domainName '{pack.domain_name}' "
                    f"does not match domain pack domainName '{domain_pack.domain_name}'"
                )
            
            # Check approved tools reference valid tools
            valid_tool_names = set(domain_pack.tools.keys())
            invalid_tools = [
                tool for tool in pack.approved_tools if tool not in valid_tool_names
            ]
            if invalid_tools:
                errors.append(
                    f"Approved tools {invalid_tools} do not exist in domain pack. "
                    f"Valid tools: {sorted(valid_tool_names)}"
                )
            
            # Check custom playbooks reference valid exception types
            valid_exception_types = set(domain_pack.exception_types.keys())
            for playbook in pack.custom_playbooks:
                if playbook.exception_type not in valid_exception_types:
                    errors.append(
                        f"Custom playbook references invalid exception type '{playbook.exception_type}'. "
                        f"Valid types: {sorted(valid_exception_types)}"
                    )
            
            # Check severity overrides reference valid exception types
            invalid_exception_types = [
                override.exception_type
                for override in pack.custom_severity_overrides
                if override.exception_type not in valid_exception_types
            ]
            if invalid_exception_types:
                errors.append(
                    f"Severity overrides reference invalid exception types: {invalid_exception_types}. "
                    f"Valid types: {sorted(valid_exception_types)}"
                )
        else:
            warnings.append(
                "Domain pack not provided for cross-reference validation. "
                "Some validations were skipped."
            )
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def _extract_tool_name_from_step(self, step: Any) -> str | None:
        """
        Extract tool name from playbook step.
        
        Args:
            step: Playbook step (can be dict or object)
            
        Returns:
            Tool name if found, None otherwise
        """
        # Handle dict
        if isinstance(step, dict):
            action = step.get("action", "")
            parameters = step.get("parameters", {})
        else:
            # Handle object with attributes
            action = getattr(step, "action", "")
            parameters = getattr(step, "parameters", {}) or {}
        
        # Check if action directly references a tool
        if isinstance(action, str):
            action_lower = action.lower()
            if "tool" in action_lower or "invoke" in action_lower:
                import re
                # Look for patterns like invokeTool('name') or toolName('name')
                match = re.search(r"['\"]([^'\"]+)['\"]", action)
                if match:
                    return match.group(1)
        
        # Check parameters for tool references
        if isinstance(parameters, dict):
            tool_keys = ["tool", "toolName", "tool_name", "action", "method"]
            for key in tool_keys:
                if key in parameters and isinstance(parameters[key], str):
                    return parameters[key]
        
        # If action looks like a direct tool name (simple identifier)
        if isinstance(action, str) and "(" not in action and " " not in action:
            return action
        
        return None

