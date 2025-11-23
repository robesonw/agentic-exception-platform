"""
Domain Pack loader and validator with strict validation rules.
Matches specification from docs/05-domain-pack-schema.md
"""

import json
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.models.domain_pack import DomainPack, Playbook, PlaybookStep


class DomainPackValidationError(Exception):
    """Raised when Domain Pack validation fails."""

    pass


def load_domain_pack(path: str) -> DomainPack:
    """
    Load a Domain Pack from a JSON file path.
    
    Args:
        path: Path to JSON file containing Domain Pack
        
    Returns:
        Validated DomainPack instance
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If JSON is invalid
        DomainPackValidationError: If validation fails
        ValidationError: If Pydantic validation fails
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Domain Pack file not found: {path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in Domain Pack file: {e.msg}", e.doc, e.pos)
    
    try:
        pack = DomainPack.model_validate(data)
    except ValidationError as e:
        raise DomainPackValidationError(f"Domain Pack schema validation failed: {e}") from e
    
    # Perform custom validation
    validate_domain_pack(pack)
    
    return pack


def validate_domain_pack(pack: DomainPack) -> None:
    """
    Validate Domain Pack with custom business rules.
    
    Validation rules:
    1. exceptionTypes must exist (at least one)
    2. playbooks must reference valid exceptionTypes
    3. tools in playbooks must exist in domainPack.tools
    
    Args:
        pack: DomainPack instance to validate
        
    Raises:
        DomainPackValidationError: If validation fails
    """
    errors: list[str] = []
    
    # Rule 1: exceptionTypes must exist
    if not pack.exception_types:
        errors.append("Domain Pack must define at least one exception type")
    
    # Rule 2: playbooks must reference valid exceptionTypes
    valid_exception_types = set(pack.exception_types.keys())
    for playbook in pack.playbooks:
        if playbook.exception_type not in valid_exception_types:
            errors.append(
                f"Playbook references invalid exception type '{playbook.exception_type}'. "
                f"Valid types: {sorted(valid_exception_types)}"
            )
    
    # Rule 3: tools referenced in playbooks must exist in domainPack.tools
    valid_tool_names = set(pack.tools.keys())
    
    for playbook in pack.playbooks:
        for step in playbook.steps:
            # Extract tool names from step action
            # Actions may be like "invokeTool('toolName')" or just "toolName"
            tool_name = _extract_tool_name_from_step(step)
            if tool_name and tool_name not in valid_tool_names:
                errors.append(
                    f"Playbook '{playbook.exception_type}' references tool '{tool_name}' "
                    f"which is not defined in domainPack.tools. "
                    f"Valid tools: {sorted(valid_tool_names)}"
                )
    
    if errors:
        error_msg = "Domain Pack validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise DomainPackValidationError(error_msg)


def _extract_tool_name_from_step(step: PlaybookStep) -> Optional[str]:
    """
    Extract tool name from playbook step.
    
    Handles various formats:
    - "invokeTool('toolName')"
    - "toolName"
    - Parameters dict with tool references
    
    Args:
        step: PlaybookStep to analyze
        
    Returns:
        Tool name if found, None otherwise
    """
    action = step.action.lower()
    
    # Check if action directly references a tool
    # Common patterns: "invokeTool", "callTool", "useTool"
    if "tool" in action:
        # Try to extract from action string
        import re
        # Look for patterns like invokeTool('name') or toolName('name')
        match = re.search(r"['\"]([^'\"]+)['\"]", step.action)
        if match:
            return match.group(1)
    
    # Check parameters for tool references
    if step.parameters:
        # Look for common tool parameter keys
        tool_keys = ["tool", "toolName", "tool_name", "action", "method"]
        for key in tool_keys:
            if key in step.parameters and isinstance(step.parameters[key], str):
                return step.parameters[key]
    
    # If action looks like a direct tool name (simple identifier)
    if step.action and "(" not in step.action and " " not in step.action:
        return step.action
    
    return None


class DomainPackRegistry:
    """
    In-memory registry for Domain Packs by domainName and version.
    Supports loading and retrieving Domain Packs.
    """

    def __init__(self):
        """Initialize the registry."""
        # Key: (domain_name, version) -> DomainPack
        self._packs: dict[tuple[str, str], DomainPack] = {}
        # Key: domain_name -> latest version DomainPack
        self._latest: dict[str, DomainPack] = {}

    def register(self, pack: DomainPack, version: str = "1.0.0") -> None:
        """
        Register a Domain Pack in the registry.
        
        Args:
            pack: DomainPack instance to register
            version: Version string (default: "1.0.0")
            
        Raises:
            DomainPackValidationError: If pack validation fails
        """
        # Validate before registering
        validate_domain_pack(pack)
        
        key = (pack.domain_name, version)
        self._packs[key] = pack
        
        # Update latest version if this is newer
        if pack.domain_name not in self._latest:
            self._latest[pack.domain_name] = pack
        else:
            # Simple version comparison (assumes semantic versioning)
            current_version = self._get_version_for_domain(pack.domain_name)
            if self._compare_versions(version, current_version) > 0:
                self._latest[pack.domain_name] = pack

    def get(self, domain_name: str, version: Optional[str] = None) -> Optional[DomainPack]:
        """
        Get a Domain Pack by domain name and optionally version.
        
        Args:
            domain_name: Domain name identifier
            version: Optional version string. If None, returns latest version.
            
        Returns:
            DomainPack instance or None if not found
        """
        if version is None:
            return self._latest.get(domain_name)
        
        return self._packs.get((domain_name, version))

    def get_latest(self, domain_name: str) -> Optional[DomainPack]:
        """
        Get the latest version of a Domain Pack.
        
        Args:
            domain_name: Domain name identifier
            
        Returns:
            Latest DomainPack instance or None if not found
        """
        return self._latest.get(domain_name)

    def list_domains(self) -> list[str]:
        """
        List all registered domain names.
        
        Returns:
            List of domain names
        """
        return sorted(set(domain for domain, _ in self._packs.keys()))

    def list_versions(self, domain_name: str) -> list[str]:
        """
        List all versions for a domain.
        
        Args:
            domain_name: Domain name identifier
            
        Returns:
            List of version strings
        """
        versions = [version for (domain, version) in self._packs.keys() if domain == domain_name]
        return sorted(versions)

    def _get_version_for_domain(self, domain_name: str) -> str:
        """Get the version string for the latest pack of a domain."""
        for (domain, version), pack in self._packs.items():
            if domain == domain_name and pack == self._latest.get(domain_name):
                return version
        return "0.0.0"

    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two version strings.
        
        Returns:
            -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
        """
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            
            # Pad to same length
            max_len = max(len(parts1), len(parts2))
            parts1.extend([0] * (max_len - len(parts1)))
            parts2.extend([0] * (max_len - len(parts2)))
            
            for p1, p2 in zip(parts1, parts2):
                if p1 < p2:
                    return -1
                elif p1 > p2:
                    return 1
            return 0
        except (ValueError, AttributeError):
            # Fallback to string comparison
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
            return 0

    def clear(self) -> None:
        """Clear all registered packs."""
        self._packs.clear()
        self._latest.clear()

    def load_from_file(self, path: str, version: Optional[str] = None) -> DomainPack:
        """
        Load a Domain Pack from file and register it.
        
        Args:
            path: Path to JSON file
            version: Optional version string. If None, attempts to extract from file.
            
        Returns:
            Loaded and registered DomainPack instance
        """
        pack = load_domain_pack(path)
        
        # Try to extract version from pack if not provided
        if version is None:
            # Check if pack has a version field (may be in extra data)
            # For now, default to 1.0.0
            version = "1.0.0"
        
        self.register(pack, version)
        return pack


# Backward compatibility: Keep DomainPackLoader class
class DomainPackLoader:
    """
    Legacy loader class for backward compatibility.
    Use DomainPackRegistry for new code.
    """

    def __init__(self):
        """Initialize the loader."""
        self._registry = DomainPackRegistry()

    def load(self, pack_data: dict) -> DomainPack:
        """
        Load a Domain Pack from dictionary.
        
        Args:
            pack_data: Dictionary containing Domain Pack data
            
        Returns:
            Validated DomainPack instance
        """
        try:
            pack = DomainPack.model_validate(pack_data)
        except ValidationError as e:
            raise DomainPackValidationError(f"Domain Pack schema validation failed: {e}") from e
        
        validate_domain_pack(pack)
        return pack

    def get(self, domain_name: str) -> Optional[DomainPack]:
        """
        Get a loaded Domain Pack by name.
        
        Args:
            domain_name: Name of the domain
            
        Returns:
            DomainPack instance or None if not found
        """
        return self._registry.get_latest(domain_name)

    def clear(self) -> None:
        """Clear all loaded packs."""
        self._registry.clear()
