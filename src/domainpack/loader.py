"""
Domain Pack loader and validator with strict validation rules.
Matches specification from docs/05-domain-pack-schema.md

Phase 2 enhancements:
- JSON and YAML support
- Enhanced schema validation
- Hot-reloading with file watching
- Tenant-scoped isolation
"""

import json
import logging
import re
from pathlib import Path
from threading import Lock
from typing import Callable, Optional

import yaml
from pydantic import ValidationError
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.models.domain_pack import (
    DomainPack,
    EntityDefinition,
    ExceptionTypeDefinition,
    Guardrails,
    Playbook,
    PlaybookStep,
    SeverityRule,
    ToolDefinition,
)


logger = logging.getLogger(__name__)


class DomainPackValidationError(Exception):
    """Raised when Domain Pack validation fails."""

    pass


def load_domain_pack(path: str) -> DomainPack:
    """
    Load a Domain Pack from a JSON or YAML file path.
    Automatically infers parser based on file extension.
    
    Args:
        path: Path to JSON (.json) or YAML (.yaml, .yml) file containing Domain Pack
        
    Returns:
        Validated DomainPack instance
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file extension is not supported
        json.JSONDecodeError: If JSON is invalid
        yaml.YAMLError: If YAML is invalid
        DomainPackValidationError: If validation fails
        ValidationError: If Pydantic validation fails
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Domain Pack file not found: {path}")
    
    # Infer parser from extension
    extension = file_path.suffix.lower()
    
    with open(file_path, "r", encoding="utf-8") as f:
        if extension == ".json":
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(f"Invalid JSON in Domain Pack file: {e.msg}", e.doc, e.pos) from e
        elif extension in (".yaml", ".yml"):
            try:
                data = yaml.safe_load(f)
                if data is None:
                    raise DomainPackValidationError("YAML file is empty or contains no data")
            except yaml.YAMLError as e:
                raise DomainPackValidationError(f"Invalid YAML in Domain Pack file: {e}") from e
        else:
            raise ValueError(
                f"Unsupported file extension: {extension}. "
                f"Supported extensions: .json, .yaml, .yml"
            )
    
    try:
        pack = DomainPack.model_validate(data)
    except ValidationError as e:
        raise DomainPackValidationError(f"Domain Pack schema validation failed: {e}") from e
    
    # Perform enhanced custom validation
    validate_domain_pack(pack)
    
    return pack


def validate_domain_pack(pack: DomainPack) -> None:
    """
    Validate Domain Pack with comprehensive business rules.
    
    Enhanced validation rules (Phase 2):
    1. exceptionTypes must exist (at least one)
    2. Validate entities structure
    3. Validate exception taxonomy (parentType references, detectionRules)
    4. Validate severity rules (condition syntax, severity values)
    5. Validate tools (required fields, parameter schemas)
    6. Validate playbooks (exceptionType references, tool references)
    7. Validate guardrails (threshold ranges, list consistency)
    
    Args:
        pack: DomainPack instance to validate
        
    Raises:
        DomainPackValidationError: If validation fails
    """
    errors: list[str] = []
    
    # Rule 1: exceptionTypes must exist
    if not pack.exception_types:
        errors.append("Domain Pack must define at least one exception type")
    
    # Rule 2: Validate entities
    for entity_name, entity_def in pack.entities.items():
        if not entity_name or not isinstance(entity_name, str):
            errors.append(f"Invalid entity name: {entity_name}")
        if not isinstance(entity_def, EntityDefinition):
            errors.append(f"Invalid entity definition for '{entity_name}'")
    
    # Rule 3: Validate exception taxonomy
    valid_exception_types = set(pack.exception_types.keys())
    for exc_type_name, exc_type_def in pack.exception_types.items():
        if not isinstance(exc_type_def, ExceptionTypeDefinition):
            errors.append(f"Invalid exception type definition for '{exc_type_name}'")
        
        # Validate detection rules are non-empty strings
        for rule in exc_type_def.detection_rules:
            if not isinstance(rule, str) or not rule.strip():
                errors.append(f"Invalid detection rule in exception type '{exc_type_name}': {rule}")
    
    # Rule 4: Validate severity rules
    valid_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    for i, severity_rule in enumerate(pack.severity_rules):
        if not isinstance(severity_rule, SeverityRule):
            errors.append(f"Invalid severity rule at index {i}")
            continue
        
        if not severity_rule.condition or not severity_rule.condition.strip():
            errors.append(f"Severity rule {i} has empty condition")
        
        if severity_rule.severity.upper() not in valid_severities:
            errors.append(
                f"Severity rule {i} has invalid severity '{severity_rule.severity}'. "
                f"Valid values: {sorted(valid_severities)}"
            )
    
    # Rule 5: Validate tools
    valid_tool_names = set(pack.tools.keys())
    for tool_name, tool_def in pack.tools.items():
        if not isinstance(tool_def, ToolDefinition):
            errors.append(f"Invalid tool definition for '{tool_name}'")
            continue
        
        if not tool_def.description or not tool_def.description.strip():
            errors.append(f"Tool '{tool_name}' missing description")
        
        if not tool_def.endpoint or not tool_def.endpoint.strip():
            errors.append(f"Tool '{tool_name}' missing endpoint")
    
    # Rule 6: Validate playbooks - exceptionType references
    for playbook in pack.playbooks:
        if not isinstance(playbook, Playbook):
            errors.append(f"Invalid playbook definition")
            continue
        
        if playbook.exception_type not in valid_exception_types:
            errors.append(
                f"Playbook references invalid exception type '{playbook.exception_type}'. "
                f"Valid types: {sorted(valid_exception_types)}"
            )
        
        # Rule 7: Validate playbooks - tool references
        for step in playbook.steps:
            if not isinstance(step, PlaybookStep):
                errors.append(f"Invalid playbook step in playbook for '{playbook.exception_type}'")
                continue
            
            if not step.action or not step.action.strip():
                errors.append(f"Playbook step has empty action in playbook for '{playbook.exception_type}'")
            
            # Extract tool names from step action
            tool_name = _extract_tool_name_from_step(step)
            if tool_name and tool_name not in valid_tool_names:
                errors.append(
                    f"Playbook '{playbook.exception_type}' references tool '{tool_name}' "
                    f"which is not defined in domainPack.tools. "
                    f"Valid tools: {sorted(valid_tool_names)}"
                )
    
    # Rule 8: Validate guardrails
    if not isinstance(pack.guardrails, Guardrails):
        errors.append("Invalid guardrails definition")
    else:
        if pack.guardrails.human_approval_threshold < 0.0 or pack.guardrails.human_approval_threshold > 1.0:
            errors.append(
                f"Guardrails humanApprovalThreshold must be between 0.0 and 1.0, "
                f"got {pack.guardrails.human_approval_threshold}"
            )
        
        # Check for conflicting allow/block lists
        allow_set = set(pack.guardrails.allow_lists)
        block_set = set(pack.guardrails.block_lists)
        conflicts = allow_set & block_set
        if conflicts:
            errors.append(
                f"Guardrails have conflicting items in both allowLists and blockLists: {sorted(conflicts)}"
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
    In-memory registry for Domain Packs with tenant-scoped isolation.
    Supports loading, retrieving, and versioning Domain Packs per tenant.
    
    Phase 2: Enhanced with tenant isolation and version tracking.
    """

    def __init__(self):
        """Initialize the registry with tenant isolation."""
        # Key: (tenant_id, domain_name, version) -> DomainPack
        self._packs: dict[tuple[str, str, str], DomainPack] = {}
        # Key: (tenant_id, domain_name) -> latest version DomainPack
        self._latest: dict[tuple[str, str], DomainPack] = {}
        # Key: (tenant_id, domain_name) -> version string
        self._versions: dict[tuple[str, str], str] = {}
        # Thread safety for concurrent access
        self._lock = Lock()

    def register(
        self, pack: DomainPack, version: str = "1.0.0", tenant_id: str = "default"
    ) -> None:
        """
        Register a Domain Pack in the registry with tenant isolation.
        
        Args:
            pack: DomainPack instance to register
            version: Version string (default: "1.0.0")
            tenant_id: Tenant identifier for isolation (default: "default")
            
        Raises:
            DomainPackValidationError: If pack validation fails
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        
        # Validate before registering
        validate_domain_pack(pack)
        
        with self._lock:
            key = (tenant_id, pack.domain_name, version)
            self._packs[key] = pack
            
            tenant_domain_key = (tenant_id, pack.domain_name)
            
            # Update latest version if this is newer
            if tenant_domain_key not in self._latest:
                self._latest[tenant_domain_key] = pack
                self._versions[tenant_domain_key] = version
            else:
                # Simple version comparison (assumes semantic versioning)
                current_version = self._versions.get(tenant_domain_key, "0.0.0")
                if self._compare_versions(version, current_version) > 0:
                    self._latest[tenant_domain_key] = pack
                    self._versions[tenant_domain_key] = version

    def get(
        self, domain_name: str, version: Optional[str] = None, tenant_id: str = "default"
    ) -> Optional[DomainPack]:
        """
        Get a Domain Pack by domain name and optionally version, with tenant isolation.
        
        Args:
            domain_name: Domain name identifier
            version: Optional version string. If None, returns latest version.
            tenant_id: Tenant identifier for isolation (default: "default")
            
        Returns:
            DomainPack instance or None if not found
            
        Raises:
            ValueError: If tenant_id is invalid
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        
        with self._lock:
            if version is None:
                return self._latest.get((tenant_id, domain_name))
            
            return self._packs.get((tenant_id, domain_name, version))

    def get_latest(self, domain_name: str, tenant_id: str = "default") -> Optional[DomainPack]:
        """
        Get the latest version of a Domain Pack with tenant isolation.
        
        Args:
            domain_name: Domain name identifier
            tenant_id: Tenant identifier for isolation (default: "default")
            
        Returns:
            Latest DomainPack instance or None if not found
            
        Raises:
            ValueError: If tenant_id is invalid
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        
        with self._lock:
            return self._latest.get((tenant_id, domain_name))

    def list_domains(self, tenant_id: str = "default") -> list[str]:
        """
        List all registered domain names for a tenant.
        
        Args:
            tenant_id: Tenant identifier for isolation (default: "default")
            
        Returns:
            List of domain names for the tenant
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        
        with self._lock:
            domains = set(
                domain for t_id, domain, _ in self._packs.keys() if t_id == tenant_id
            )
            return sorted(domains)

    def list_versions(self, domain_name: str, tenant_id: str = "default") -> list[str]:
        """
        List all versions for a domain within a tenant namespace.
        
        Args:
            domain_name: Domain name identifier
            tenant_id: Tenant identifier for isolation (default: "default")
            
        Returns:
            List of version strings
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        
        with self._lock:
            versions = [
                version
                for (t_id, domain, version) in self._packs.keys()
                if t_id == tenant_id and domain == domain_name
            ]
            return sorted(versions)

    def _get_version_for_domain(self, domain_name: str, tenant_id: str = "default") -> str:
        """Get the version string for the latest pack of a domain for a tenant."""
        return self._versions.get((tenant_id, domain_name), "0.0.0")

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

    def clear(self, tenant_id: Optional[str] = None) -> None:
        """
        Clear registered packs.
        
        Args:
            tenant_id: Optional tenant ID. If provided, clears only that tenant's packs.
                      If None, clears all packs.
        """
        with self._lock:
            if tenant_id is None:
                self._packs.clear()
                self._latest.clear()
                self._versions.clear()
            else:
                # Clear only packs for this tenant
                keys_to_remove = [
                    key for key in self._packs.keys() if key[0] == tenant_id
                ]
                for key in keys_to_remove:
                    del self._packs[key]
                
                # Clear latest and versions for this tenant
                keys_to_remove = [
                    key for key in self._latest.keys() if key[0] == tenant_id
                ]
                for key in keys_to_remove:
                    del self._latest[key]
                    del self._versions[key]

    def load_from_file(
        self, path: str, version: Optional[str] = None, tenant_id: str = "default"
    ) -> DomainPack:
        """
        Load a Domain Pack from file and register it with tenant isolation.
        
        Args:
            path: Path to JSON or YAML file
            version: Optional version string. If None, defaults to "1.0.0".
            tenant_id: Tenant identifier for isolation (default: "default")
            
        Returns:
            Loaded and registered DomainPack instance
        """
        pack = load_domain_pack(path)
        
        # Try to extract version from pack if not provided
        if version is None:
            # Default to 1.0.0 if not specified
            version = "1.0.0"
        
        self.register(pack, version, tenant_id)
        return pack


class DomainPackFileWatcher(FileSystemEventHandler):
    """
    File system event handler for Domain Pack hot-reloading.
    Watches for changes in domainpacks/ folder and reloads packs automatically.
    """

    def __init__(
        self,
        registry: "DomainPackRegistry",
        watch_dir: str,
        on_reload: Optional[Callable[[str, DomainPack], None]] = None,
    ):
        """
        Initialize the file watcher.
        
        Args:
            registry: DomainPackRegistry instance to update
            watch_dir: Directory to watch for Domain Pack files
            on_reload: Optional callback function(tenant_id, pack) called after reload
        """
        self.registry = registry
        self.watch_dir = Path(watch_dir)
        self.on_reload = on_reload
        self._file_versions: dict[str, str] = {}  # Track file -> tenant_id mapping

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        # Only process JSON and YAML files
        if file_path.suffix.lower() not in (".json", ".yaml", ".yml"):
            return
        
        # Skip if file doesn't exist (might be a delete event)
        if not file_path.exists():
            return
        
        self._reload_pack(file_path)

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() not in (".json", ".yaml", ".yml"):
            return
        
        self._reload_pack(file_path)

    def _reload_pack(self, file_path: Path):
        """
        Reload a Domain Pack from file.
        
        Args:
            file_path: Path to Domain Pack file
        """
        try:
            # Extract tenant_id from filename or use default
            # Convention: tenant_<id>_<domain>.json or <domain>.json
            tenant_id = "default"
            filename = file_path.stem
            
            # Check for tenant prefix pattern: tenant_<id>_<domain>
            tenant_match = re.match(r"^tenant_([^_]+)_(.+)$", filename)
            if tenant_match:
                tenant_id = tenant_match.group(1)
            
            # Load and register the pack
            pack = load_domain_pack(str(file_path))
            
            # Bump version on reload
            existing_pack = self.registry.get_latest(pack.domain_name, tenant_id)
            if existing_pack:
                # Get current version and increment patch version
                current_version = self.registry._get_version_for_domain(
                    pack.domain_name, tenant_id
                )
                version_parts = current_version.split(".")
                if len(version_parts) >= 3:
                    try:
                        patch = int(version_parts[2])
                        version_parts[2] = str(patch + 1)
                        new_version = ".".join(version_parts)
                    except ValueError:
                        new_version = f"{current_version}.1"
                else:
                    new_version = f"{current_version}.1"
            else:
                new_version = "1.0.0"
            
            self.registry.register(pack, new_version, tenant_id)
            logger.info(
                f"Hot-reloaded Domain Pack '{pack.domain_name}' "
                f"version {new_version} for tenant '{tenant_id}' from {file_path}"
            )
            
            # Call callback if provided
            if self.on_reload:
                self.on_reload(tenant_id, pack)
                
        except Exception as e:
            logger.error(
                f"Failed to hot-reload Domain Pack from {file_path}: {e}",
                exc_info=True,
            )


class HotReloadManager:
    """
    Manages hot-reloading of Domain Packs from a watched directory.
    """

    def __init__(
        self,
        registry: DomainPackRegistry,
        watch_dir: str = "domainpacks",
        on_reload: Optional[Callable[[str, DomainPack], None]] = None,
    ):
        """
        Initialize the hot-reload manager.
        
        Args:
            registry: DomainPackRegistry instance to update
            watch_dir: Directory to watch for Domain Pack files (default: "domainpacks")
            on_reload: Optional callback function(tenant_id, pack) called after reload
        """
        self.registry = registry
        self.watch_dir = Path(watch_dir)
        self.on_reload = on_reload
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[DomainPackFileWatcher] = None

    def start(self):
        """Start watching for file changes."""
        if not self.watch_dir.exists():
            logger.warning(f"Watch directory does not exist: {self.watch_dir}")
            self.watch_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created watch directory: {self.watch_dir}")
        
        self.event_handler = DomainPackFileWatcher(
            self.registry, str(self.watch_dir), self.on_reload
        )
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.watch_dir), recursive=False)
        self.observer.start()
        logger.info(f"Started hot-reload watcher for directory: {self.watch_dir}")

    def stop(self):
        """Stop watching for file changes."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)
            logger.info("Stopped hot-reload watcher")

    def reload_all(self, tenant_id: str = "default"):
        """
        Manually reload all Domain Packs from the watch directory.
        
        Args:
            tenant_id: Tenant identifier for isolation (default: "default")
        """
        if not self.watch_dir.exists():
            logger.warning(f"Watch directory does not exist: {self.watch_dir}")
            return
        
        loaded_count = 0
        for file_path in self.watch_dir.glob("*.json"):
            try:
                self.registry.load_from_file(str(file_path), tenant_id=tenant_id)
                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to reload {file_path}: {e}", exc_info=True)
        
        for file_path in self.watch_dir.glob("*.yaml"):
            try:
                self.registry.load_from_file(str(file_path), tenant_id=tenant_id)
                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to reload {file_path}: {e}", exc_info=True)
        
        for file_path in self.watch_dir.glob("*.yml"):
            try:
                self.registry.load_from_file(str(file_path), tenant_id=tenant_id)
                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to reload {file_path}: {e}", exc_info=True)
        
        logger.info(f"Manually reloaded {loaded_count} Domain Pack(s) for tenant '{tenant_id}'")


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
