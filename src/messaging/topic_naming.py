"""
Topic Naming Strategy for Phase 9.

Defines topic naming conventions for tenant isolation.

Phase 9 P9-23: Tenant isolation at message broker layer.
Reference: docs/phase9-tenant-isolation-broker.md
"""

from typing import Optional


class TopicNamingStrategy:
    """
    Topic naming strategy for tenant isolation.
    
    Supports two strategies:
    - Option A (MVP): Shared topics + strict tenant validation
    - Option B (Future): Per-tenant topics
    """
    
    # Option A: Shared topics (MVP)
    TOPIC_EXCEPTIONS = "exceptions"
    TOPIC_SLA = "sla"
    TOPIC_PLAYBOOKS = "playbooks"
    TOPIC_TOOLS = "tools"
    
    @staticmethod
    def get_topic_exceptions(tenant_id: Optional[str] = None) -> str:
        """
        Get exceptions topic name.
        
        Option A (MVP): Returns shared topic "exceptions"
        Option B (Future): Returns per-tenant topic "exceptions.{tenant_id}"
        
        Args:
            tenant_id: Optional tenant identifier (for Option B)
            
        Returns:
            Topic name
        """
        if tenant_id:
            # Option B: Per-tenant topic
            return f"exceptions.{tenant_id}"
        # Option A: Shared topic
        return TopicNamingStrategy.TOPIC_EXCEPTIONS
    
    @staticmethod
    def get_topic_sla(tenant_id: Optional[str] = None) -> str:
        """
        Get SLA topic name.
        
        Option A (MVP): Returns shared topic "sla"
        Option B (Future): Returns per-tenant topic "sla.{tenant_id}"
        
        Args:
            tenant_id: Optional tenant identifier (for Option B)
            
        Returns:
            Topic name
        """
        if tenant_id:
            # Option B: Per-tenant topic
            return f"sla.{tenant_id}"
        # Option A: Shared topic
        return TopicNamingStrategy.TOPIC_SLA
    
    @staticmethod
    def get_topic_playbooks(tenant_id: Optional[str] = None) -> str:
        """
        Get playbooks topic name.
        
        Option A (MVP): Returns shared topic "playbooks"
        Option B (Future): Returns per-tenant topic "playbooks.{tenant_id}"
        
        Args:
            tenant_id: Optional tenant identifier (for Option B)
            
        Returns:
            Topic name
        """
        if tenant_id:
            # Option B: Per-tenant topic
            return f"playbooks.{tenant_id}"
        # Option A: Shared topic
        return TopicNamingStrategy.TOPIC_PLAYBOOKS
    
    @staticmethod
    def get_topic_tools(tenant_id: Optional[str] = None) -> str:
        """
        Get tools topic name.
        
        Option A (MVP): Returns shared topic "tools"
        Option B (Future): Returns per-tenant topic "tools.{tenant_id}"
        
        Args:
            tenant_id: Optional tenant identifier (for Option B)
            
        Returns:
            Topic name
        """
        if tenant_id:
            # Option B: Per-tenant topic
            return f"tools.{tenant_id}"
        # Option A: Shared topic
        return TopicNamingStrategy.TOPIC_TOOLS
    
    @staticmethod
    def extract_tenant_id_from_topic(topic: str) -> Optional[str]:
        """
        Extract tenant_id from topic name (for Option B).
        
        Args:
            topic: Topic name (e.g., "exceptions.tenant_001")
            
        Returns:
            Tenant ID if topic follows per-tenant pattern, None otherwise
        """
        # Check if topic follows per-tenant pattern: "{base}.{tenant_id}"
        parts = topic.split(".", 1)
        if len(parts) == 2:
            base, tenant_id = parts
            # Validate base is a known topic
            known_bases = [
                TopicNamingStrategy.TOPIC_EXCEPTIONS,
                TopicNamingStrategy.TOPIC_SLA,
                TopicNamingStrategy.TOPIC_PLAYBOOKS,
                TopicNamingStrategy.TOPIC_TOOLS,
            ]
            if base in known_bases:
                return tenant_id
        return None
    
    @staticmethod
    def is_per_tenant_topic(topic: str) -> bool:
        """
        Check if topic follows per-tenant naming pattern (Option B).
        
        Args:
            topic: Topic name
            
        Returns:
            True if topic follows per-tenant pattern, False otherwise
        """
        return TopicNamingStrategy.extract_tenant_id_from_topic(topic) is not None



