"""
SLO/SLA Configuration (P3-25).

Defines SLO targets per tenant and domain, loaded from YAML configuration files.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


@dataclass
class SLOConfig:
    """
    SLO configuration for a tenant and domain.
    
    Defines target thresholds for:
    - Latency (p95 in milliseconds)
    - Error rate (percentage)
    - MTTR (Mean Time To Resolution in minutes)
    - Auto-resolution rate (percentage)
    - Throughput (exceptions per second, optional)
    """

    tenant_id: str
    domain: Optional[str] = None
    target_latency_ms: float = 1000.0  # Default: 1 second p95 latency
    target_error_rate: float = 0.01  # Default: 1% error rate
    target_mttr_minutes: float = 30.0  # Default: 30 minutes MTTR
    target_auto_resolution_rate: float = 0.80  # Default: 80% auto-resolution
    target_throughput: Optional[float] = None  # Optional: exceptions per second
    window_minutes: int = 60  # Time window for SLO evaluation (default: 1 hour)

    def to_dict(self) -> dict:
        """Convert SLO config to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "domain": self.domain,
            "target_latency_ms": self.target_latency_ms,
            "target_error_rate": self.target_error_rate,
            "target_mttr_minutes": self.target_mttr_minutes,
            "target_auto_resolution_rate": self.target_auto_resolution_rate,
            "target_throughput": self.target_throughput,
            "window_minutes": self.window_minutes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SLOConfig":
        """Create SLO config from dictionary."""
        return cls(
            tenant_id=data["tenant_id"],
            domain=data.get("domain"),
            target_latency_ms=data.get("target_latency_ms", 1000.0),
            target_error_rate=data.get("target_error_rate", 0.01),
            target_mttr_minutes=data.get("target_mttr_minutes", 30.0),
            target_auto_resolution_rate=data.get("target_auto_resolution_rate", 0.80),
            target_throughput=data.get("target_throughput"),
            window_minutes=data.get("window_minutes", 60),
        )


class SLOConfigLoader:
    """
    Loader for SLO configurations from YAML files.
    
    Looks for config files at: ./config/slo/{tenantId}_{domain}.yaml
    Falls back to defaults if file not found.
    """

    def __init__(self, config_dir: str = "config/slo"):
        """
        Initialize SLO config loader.
        
        Args:
            config_dir: Directory containing SLO config files (default: "config/slo")
        """
        self.config_dir = Path(config_dir)
        self._cache: dict[tuple[str, Optional[str]], SLOConfig] = {}

    def load_config(
        self, tenant_id: str, domain: Optional[str] = None
    ) -> SLOConfig:
        """
        Load SLO config for tenant and domain.
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain name
            
        Returns:
            SLOConfig instance (from file or defaults)
        """
        cache_key = (tenant_id, domain)
        
        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Try to load from file
        config = self._load_from_file(tenant_id, domain)
        
        # Cache it
        self._cache[cache_key] = config
        
        return config

    def _load_from_file(
        self, tenant_id: str, domain: Optional[str] = None
    ) -> SLOConfig:
        """
        Load SLO config from YAML file.
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain name
            
        Returns:
            SLOConfig instance
        """
        # Build filename
        if domain:
            filename = f"{tenant_id}_{domain}.yaml"
        else:
            filename = f"{tenant_id}.yaml"
        
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            logger.debug(
                f"SLO config not found at {config_path}, using defaults for "
                f"tenant {tenant_id}, domain {domain}"
            )
            return SLOConfig(tenant_id=tenant_id, domain=domain)
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not data:
                logger.warning(f"Empty SLO config file at {config_path}, using defaults")
                return SLOConfig(tenant_id=tenant_id, domain=domain)
            
            # Merge with defaults
            config_data = {
                "tenant_id": tenant_id,
                "domain": domain,
                "target_latency_ms": data.get("target_latency_ms", 1000.0),
                "target_error_rate": data.get("target_error_rate", 0.01),
                "target_mttr_minutes": data.get("target_mttr_minutes", 30.0),
                "target_auto_resolution_rate": data.get(
                    "target_auto_resolution_rate", 0.80
                ),
                "target_throughput": data.get("target_throughput"),
                "window_minutes": data.get("window_minutes", 60),
            }
            
            config = SLOConfig.from_dict(config_data)
            logger.info(
                f"Loaded SLO config from {config_path} for tenant {tenant_id}, "
                f"domain {domain}"
            )
            return config
            
        except Exception as e:
            logger.error(
                f"Failed to load SLO config from {config_path}: {e}, using defaults",
                exc_info=True,
            )
            return SLOConfig(tenant_id=tenant_id, domain=domain)

    def clear_cache(self) -> None:
        """Clear the config cache."""
        self._cache.clear()


# Global loader instance
_slo_config_loader: Optional[SLOConfigLoader] = None


def get_slo_config_loader() -> SLOConfigLoader:
    """
    Get global SLO config loader instance.
    
    Returns:
        SLOConfigLoader instance
    """
    global _slo_config_loader
    if _slo_config_loader is None:
        _slo_config_loader = SLOConfigLoader()
    return _slo_config_loader


def load_slo_config(tenant_id: str, domain: Optional[str] = None) -> SLOConfig:
    """
    Load SLO config for tenant and domain.
    
    Args:
        tenant_id: Tenant identifier
        domain: Optional domain name
        
    Returns:
        SLOConfig instance
    """
    loader = get_slo_config_loader()
    return loader.load_config(tenant_id, domain)

