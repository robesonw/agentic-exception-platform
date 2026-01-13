"""
Platform Settings Repository - Database access for platform-wide settings.

Provides CRUD operations for the platform_settings table with type-aware
value handling and audit support.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import PlatformSetting

logger = logging.getLogger(__name__)


class PlatformSettingsRepository:
    """
    Repository for platform-wide settings.
    
    Handles typed value storage (string, boolean, number, json, timestamp)
    and provides audit trail for changes.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get(self, key: str) -> Optional[dict[str, Any]]:
        """
        Get a setting by key.
        
        Args:
            key: Setting key.
            
        Returns:
            Dict with key, value, type, and metadata or None if not found.
        """
        result = await self.session.execute(
            select(PlatformSetting).where(PlatformSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if not setting:
            return None
        
        return self._setting_to_dict(setting)
    
    async def get_value(self, key: str, default: Any = None) -> Any:
        """
        Get just the value for a setting.
        
        Args:
            key: Setting key.
            default: Default value if not found.
            
        Returns:
            Setting value or default.
        """
        result = await self.get(key)
        if result is None:
            return default
        return result.get("value", default)
    
    async def get_all(self, prefix: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Get all settings, optionally filtered by prefix.
        
        Args:
            prefix: Optional key prefix filter (e.g., "demo.").
            
        Returns:
            List of setting dicts.
        """
        query = select(PlatformSetting)
        if prefix:
            query = query.where(PlatformSetting.key.like(f"{prefix}%"))
        query = query.order_by(PlatformSetting.key)
        
        result = await self.session.execute(query)
        settings = result.scalars().all()
        
        return [self._setting_to_dict(s) for s in settings]
    
    async def set(
        self,
        key: str,
        value: Any,
        value_type: Optional[str] = None,
        description: Optional[str] = None,
        updated_by: Optional[str] = None,
        audit_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Set a setting value (upsert).
        
        Args:
            key: Setting key.
            value: Setting value.
            value_type: Value type hint (auto-detected if not provided).
            description: Optional description.
            updated_by: User/system making the change.
            audit_reason: Reason for the change.
            
        Returns:
            Updated setting dict.
        """
        # Auto-detect type if not provided
        if value_type is None:
            value_type = self._detect_type(value)
        
        # Serialize value
        value_json, value_text = self._serialize_value(value, value_type)
        
        # Check if exists
        result = await self.session.execute(
            select(PlatformSetting).where(PlatformSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            # Update existing
            setting.value_json = value_json
            setting.value_text = value_text
            setting.value_type = value_type
            if description is not None:
                setting.description = description
            setting.updated_at = datetime.now(timezone.utc)
            setting.updated_by = updated_by
            setting.audit_reason = audit_reason
        else:
            # Create new
            setting = PlatformSetting(
                key=key,
                value_json=value_json,
                value_text=value_text,
                value_type=value_type,
                description=description,
                updated_by=updated_by,
                audit_reason=audit_reason,
            )
            self.session.add(setting)
        
        await self.session.flush()
        
        logger.info(f"Set platform setting: {key} = {value} (type={value_type})")
        
        return self._setting_to_dict(setting)
    
    async def set_many(
        self,
        settings: dict[str, Any],
        updated_by: Optional[str] = None,
        audit_reason: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Set multiple settings at once.
        
        Args:
            settings: Dict of key -> value pairs.
            updated_by: User/system making the change.
            audit_reason: Reason for the change.
            
        Returns:
            List of updated setting dicts.
        """
        results = []
        for key, value in settings.items():
            result = await self.set(
                key=key,
                value=value,
                updated_by=updated_by,
                audit_reason=audit_reason,
            )
            results.append(result)
        return results
    
    async def delete(self, key: str) -> bool:
        """
        Delete a setting.
        
        Args:
            key: Setting key.
            
        Returns:
            True if deleted, False if not found.
        """
        result = await self.session.execute(
            delete(PlatformSetting).where(PlatformSetting.key == key)
        )
        deleted = result.rowcount > 0
        
        if deleted:
            logger.info(f"Deleted platform setting: {key}")
        
        return deleted
    
    async def ensure_defaults(
        self,
        defaults: dict[str, tuple[Any, str, Optional[str]]],
        updated_by: str = "system",
    ) -> int:
        """
        Ensure default settings exist (won't overwrite existing).
        
        Args:
            defaults: Dict of key -> (value, type, description) tuples.
            updated_by: User/system for audit.
            
        Returns:
            Number of settings created.
        """
        created = 0
        for key, (value, value_type, description) in defaults.items():
            existing = await self.get(key)
            if existing is None:
                await self.set(
                    key=key,
                    value=value,
                    value_type=value_type,
                    description=description,
                    updated_by=updated_by,
                    audit_reason="Default initialization",
                )
                created += 1
        
        if created > 0:
            logger.info(f"Created {created} default platform settings")
        
        return created
    
    def _setting_to_dict(self, setting: PlatformSetting) -> dict[str, Any]:
        """Convert setting model to dict with deserialized value."""
        value = self._deserialize_value(
            setting.value_json,
            setting.value_text,
            setting.value_type,
        )
        
        return {
            "key": setting.key,
            "value": value,
            "type": setting.value_type,
            "description": setting.description,
            "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
            "updated_by": setting.updated_by,
            "audit_reason": setting.audit_reason,
        }
    
    def _detect_type(self, value: Any) -> str:
        """Auto-detect value type."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "number"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, (dict, list)):
            return "json"
        elif isinstance(value, datetime):
            return "timestamp"
        else:
            return "string"
    
    def _serialize_value(self, value: Any, value_type: str) -> tuple[Optional[dict], Optional[str]]:
        """
        Serialize value for storage.
        
        Returns (value_json, value_text) tuple.
        """
        if value_type == "json":
            return value if isinstance(value, (dict, list)) else None, None
        elif value_type == "boolean":
            return {"value": bool(value)}, None
        elif value_type == "number":
            return {"value": value}, None
        elif value_type == "timestamp":
            if isinstance(value, datetime):
                return None, value.isoformat()
            return None, str(value)
        else:
            return None, str(value)
    
    def _deserialize_value(
        self,
        value_json: Optional[dict],
        value_text: Optional[str],
        value_type: str,
    ) -> Any:
        """Deserialize stored value to appropriate type."""
        if value_type == "json":
            return value_json
        elif value_type == "boolean":
            if value_json and "value" in value_json:
                return bool(value_json["value"])
            return value_text.lower() in ("true", "1", "yes") if value_text else False
        elif value_type == "number":
            if value_json and "value" in value_json:
                return value_json["value"]
            try:
                return float(value_text) if value_text and "." in value_text else int(value_text)
            except (ValueError, TypeError):
                return 0
        elif value_type == "timestamp":
            if value_text:
                try:
                    return datetime.fromisoformat(value_text)
                except ValueError:
                    return None
            return None
        else:
            return value_text
