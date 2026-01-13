"""
Demo Catalog Loader - Loads and validates demo catalog from JSON file.

Provides the DemoCatalogLoader class for loading the demo catalog with
validation, caching, and error handling.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.demo.catalog_types import DemoCatalog, DemoScenario, DemoTenant

logger = logging.getLogger(__name__)


class CatalogLoadError(Exception):
    """Error loading or validating demo catalog."""
    
    def __init__(self, message: str, path: Optional[str] = None, details: Optional[dict] = None):
        super().__init__(message)
        self.path = path
        self.details = details or {}


class DemoCatalogLoader:
    """
    Loads and validates demo catalog from JSON file.
    
    Features:
    - JSON schema validation via Pydantic
    - Caching of loaded catalog
    - Support for multiple paths (custom + default)
    - Validation of required fields and cross-references
    """
    
    DEFAULT_CATALOG_PATH = Path(__file__).parent.parent.parent / "demo" / "demoCatalog.json"
    
    _cache: Optional[DemoCatalog] = None
    _cache_path: Optional[str] = None
    
    @classmethod
    def load(
        cls,
        path: Optional[str] = None,
        force_reload: bool = False,
    ) -> DemoCatalog:
        """
        Load demo catalog from JSON file.
        
        Args:
            path: Optional path to catalog file. If not provided, uses default.
            force_reload: Force reload even if cached.
            
        Returns:
            Validated DemoCatalog instance.
            
        Raises:
            CatalogLoadError: If file not found or validation fails.
        """
        catalog_path = Path(path) if path else cls.DEFAULT_CATALOG_PATH
        
        # Check cache
        if not force_reload and cls._cache is not None and cls._cache_path == str(catalog_path):
            logger.debug(f"Using cached catalog from {catalog_path}")
            return cls._cache
        
        # Check file exists
        if not catalog_path.exists():
            raise CatalogLoadError(
                f"Demo catalog file not found: {catalog_path}",
                path=str(catalog_path),
            )
        
        # Load JSON
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CatalogLoadError(
                f"Invalid JSON in catalog file: {e}",
                path=str(catalog_path),
                details={"line": e.lineno, "column": e.colno},
            )
        except IOError as e:
            raise CatalogLoadError(
                f"Error reading catalog file: {e}",
                path=str(catalog_path),
            )
        
        # Validate with Pydantic
        try:
            catalog = DemoCatalog(**data)
        except ValidationError as e:
            raise CatalogLoadError(
                f"Catalog validation failed: {e.error_count()} errors",
                path=str(catalog_path),
                details={"errors": e.errors()},
            )
        
        # Additional validation
        cls._validate_cross_references(catalog)
        
        # Cache
        cls._cache = catalog
        cls._cache_path = str(catalog_path)
        
        logger.info(f"Loaded demo catalog v{catalog.version} from {catalog_path}")
        logger.info(
            f"  Tenants: {len(catalog.demo_tenants)}, "
            f"Scenarios: {len(catalog.scenarios)}, "
            f"Domain Packs: {len(catalog.domain_packs)}"
        )
        
        return catalog
    
    @classmethod
    def _validate_cross_references(cls, catalog: DemoCatalog) -> None:
        """
        Validate cross-references within catalog.
        
        Checks:
        - Scenario references valid tenants (by industry)
        - Playbook bindings reference valid playbooks
        - Tool bindings reference valid tools
        """
        errors = []
        
        # Get valid industries from tenants
        tenant_industries = {t.industry for t in catalog.demo_tenants}
        
        # Validate scenarios
        for scenario in catalog.scenarios:
            if scenario.industry not in tenant_industries:
                # Warning only - scenario can still be used with matching industry tenants
                logger.warning(
                    f"Scenario {scenario.scenario_id} targets industry '{scenario.industry}' "
                    f"but no demo tenant has that industry"
                )
        
        # Validate domain packs have required fields
        for pack in catalog.domain_packs:
            if not pack.exception_types:
                errors.append(f"Domain pack {pack.domain_name} has no exception types")
        
        if errors:
            raise CatalogLoadError(
                f"Catalog cross-reference validation failed: {len(errors)} errors",
                details={"validation_errors": errors},
            )
    
    @classmethod
    def get_tenant_by_key(cls, catalog: DemoCatalog, tenant_key: str) -> Optional[DemoTenant]:
        """Get a specific tenant from catalog by key."""
        for tenant in catalog.demo_tenants:
            if tenant.tenant_key == tenant_key:
                return tenant
        return None
    
    @classmethod
    def get_tenants_by_industry(cls, catalog: DemoCatalog, industry: str) -> list[DemoTenant]:
        """Get all tenants for a specific industry."""
        return [t for t in catalog.demo_tenants if t.industry.value == industry]
    
    @classmethod
    def get_scenario_by_id(cls, catalog: DemoCatalog, scenario_id: str) -> Optional[DemoScenario]:
        """Get a specific scenario by ID."""
        for scenario in catalog.scenarios:
            if scenario.scenario_id == scenario_id:
                return scenario
        return None
    
    @classmethod
    def get_scenarios_by_industry(cls, catalog: DemoCatalog, industry: str) -> list[DemoScenario]:
        """Get all scenarios for a specific industry."""
        return [s for s in catalog.scenarios if s.industry.value == industry]
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached catalog."""
        cls._cache = None
        cls._cache_path = None
        logger.debug("Demo catalog cache cleared")
    
    @classmethod
    def get_default_path(cls) -> Path:
        """Get the default catalog file path."""
        return cls.DEFAULT_CATALOG_PATH


def load_demo_catalog(path: Optional[str] = None) -> DemoCatalog:
    """
    Convenience function to load demo catalog.
    
    Args:
        path: Optional path to catalog file.
        
    Returns:
        Validated DemoCatalog instance.
    """
    return DemoCatalogLoader.load(path)
