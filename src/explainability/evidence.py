"""
Evidence Tracking and Attribution System (P3-29).

Tracks evidence items (RAG results, tool outputs, policy rules) and links them
to agent decisions for full explainability.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class EvidenceType(str, Enum):
    """Types of evidence items."""

    RAG = "rag"
    TOOL = "tool"
    POLICY = "policy"
    MANUAL = "manual"


class EvidenceInfluence(str, Enum):
    """How evidence influences a decision."""

    SUPPORT = "support"  # Evidence supports the decision
    CONTRADICT = "contradict"  # Evidence contradicts the decision
    CONTEXTUAL = "contextual"  # Evidence provides context but doesn't directly support/contradict


class EvidenceItem(BaseModel):
    """
    A single piece of evidence used in decision-making.
    
    Can be from RAG, tool execution, policy rules, or manual input.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique evidence identifier"
    )
    type: EvidenceType = Field(..., description="Type of evidence (rag, tool, policy, manual)")
    source_id: str = Field(..., alias="sourceId", description="Source identifier (document ID, tool name, rule ID, etc.)")
    description: str = Field(..., description="Human-readable description of the evidence")
    payload_ref: Optional[str] = Field(
        None, alias="payloadRef", description="Reference to full payload (file path, URL, etc.)"
    )
    similarity_score: Optional[float] = Field(
        None, alias="similarityScore", ge=0.0, le=1.0, description="Similarity score (for RAG evidence)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="createdAt",
        description="Evidence creation timestamp",
    )
    tenant_id: Optional[str] = Field(
        None, alias="tenantId", description="Tenant identifier"
    )
    exception_id: Optional[str] = Field(
        None, alias="exceptionId", description="Exception identifier"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional evidence metadata"
    )


class EvidenceLink(BaseModel):
    """
    Links an evidence item to an agent decision.
    
    Tracks how evidence influenced a decision.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique link identifier"
    )
    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier")
    agent_name: str = Field(..., alias="agentName", description="Agent name (e.g., 'TriageAgent')")
    stage_name: str = Field(..., alias="stageName", description="Pipeline stage name (e.g., 'triage')")
    evidence_id: str = Field(..., alias="evidenceId", description="Evidence item identifier")
    influence: EvidenceInfluence = Field(
        default=EvidenceInfluence.SUPPORT, description="How evidence influences the decision"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="createdAt",
        description="Link creation timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional link metadata"
    )


class EvidenceTracker:
    """
    Tracks evidence items and links for exceptions.
    
    Records evidence from RAG, tools, and policy systems,
    and links them to agent decisions.
    """

    def __init__(self, storage_dir: str = "./runtime/evidence"):
        """
        Initialize evidence tracker.
        
        Args:
            storage_dir: Directory for storing evidence records
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for quick lookups
        self._evidence_cache: dict[str, EvidenceItem] = {}
        self._links_cache: dict[str, list[EvidenceLink]] = {}

    def record_evidence_item(
        self,
        evidence_type: EvidenceType,
        source_id: str,
        description: str,
        tenant_id: Optional[str] = None,
        exception_id: Optional[str] = None,
        similarity_score: Optional[float] = None,
        payload_ref: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> EvidenceItem:
        """
        Record an evidence item.
        
        Args:
            evidence_type: Type of evidence (rag, tool, policy, manual)
            source_id: Source identifier
            description: Human-readable description
            tenant_id: Optional tenant identifier
            exception_id: Optional exception identifier
            similarity_score: Optional similarity score (for RAG)
            payload_ref: Optional reference to full payload
            metadata: Optional additional metadata
            
        Returns:
            EvidenceItem instance
        """
        evidence = EvidenceItem(
            type=evidence_type,
            source_id=source_id,
            description=description,
            tenant_id=tenant_id,
            exception_id=exception_id,
            similarity_score=similarity_score,
            payload_ref=payload_ref,
            metadata=metadata or {},
        )
        
        # Cache evidence
        self._evidence_cache[evidence.id] = evidence
        
        # Persist evidence
        self._persist_evidence(evidence)
        
        logger.debug(
            f"Recorded evidence item {evidence.id} (type={evidence_type.value}, "
            f"source={source_id})"
        )
        
        return evidence

    def link_evidence_to_decision(
        self,
        exception_id: str,
        agent_name: str,
        stage_name: str,
        evidence_id: str,
        influence: EvidenceInfluence = EvidenceInfluence.SUPPORT,
        metadata: Optional[dict[str, Any]] = None,
    ) -> EvidenceLink:
        """
        Link an evidence item to an agent decision.
        
        Args:
            exception_id: Exception identifier
            agent_name: Agent name
            stage_name: Pipeline stage name
            evidence_id: Evidence item identifier
            influence: How evidence influences the decision
            metadata: Optional additional metadata
            
        Returns:
            EvidenceLink instance
        """
        link = EvidenceLink(
            exception_id=exception_id,
            agent_name=agent_name,
            stage_name=stage_name,
            evidence_id=evidence_id,
            influence=influence,
            metadata=metadata or {},
        )
        
        # Cache link
        cache_key = f"{exception_id}_{stage_name}"
        if cache_key not in self._links_cache:
            self._links_cache[cache_key] = []
        self._links_cache[cache_key].append(link)
        
        # Persist link
        self._persist_link(link)
        
        logger.debug(
            f"Linked evidence {evidence_id} to {agent_name} decision "
            f"(exception={exception_id}, stage={stage_name}, influence={influence.value})"
        )
        
        return link

    def get_evidence_for_exception(
        self, exception_id: str, tenant_id: Optional[str] = None
    ) -> list[EvidenceItem]:
        """
        Get all evidence items for an exception.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Optional tenant identifier for filtering
            
        Returns:
            List of EvidenceItem instances
        """
        # Try cache first
        evidence_items = [
            ev for ev in self._evidence_cache.values()
            if ev.exception_id == exception_id
            and (tenant_id is None or ev.tenant_id == tenant_id)
        ]
        
        # Also load from storage
        storage_evidence = self._load_evidence_from_storage(exception_id, tenant_id)
        
        # Merge and deduplicate
        seen_ids = {ev.id for ev in evidence_items}
        for ev in storage_evidence:
            if ev.id not in seen_ids:
                evidence_items.append(ev)
                seen_ids.add(ev.id)
        
        return evidence_items

    def get_evidence_links_for_exception(
        self, exception_id: str, stage_name: Optional[str] = None
    ) -> list[EvidenceLink]:
        """
        Get all evidence links for an exception.
        
        Args:
            exception_id: Exception identifier
            stage_name: Optional stage name filter
            
        Returns:
            List of EvidenceLink instances
        """
        # Try cache first
        cache_key = f"{exception_id}_{stage_name or '*'}"
        links = []
        
        if stage_name:
            links = [
                link for key, link_list in self._links_cache.items()
                if key.startswith(f"{exception_id}_") and key.endswith(f"_{stage_name}")
                for link in link_list
            ]
        else:
            links = [
                link for key, link_list in self._links_cache.items()
                if key.startswith(f"{exception_id}_")
                for link in link_list
            ]
        
        # Also load from storage
        storage_links = self._load_links_from_storage(exception_id, stage_name)
        
        # Merge and deduplicate
        seen_ids = {link.id for link in links}
        for link in storage_links:
            if link.id not in seen_ids:
                links.append(link)
                seen_ids.add(link.id)
        
        return links

    def _persist_evidence(self, evidence: EvidenceItem) -> None:
        """Persist evidence item to storage."""
        if not evidence.exception_id or not evidence.tenant_id:
            # Can't persist without exception_id and tenant_id
            return
        
        evidence_file = self.storage_dir / f"{evidence.tenant_id}_{evidence.exception_id}_evidence.jsonl"
        
        try:
            with open(evidence_file, "a", encoding="utf-8") as f:
                evidence_dict = evidence.model_dump(by_alias=True, mode="json")
                f.write(json.dumps(evidence_dict, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist evidence: {e}", exc_info=True)

    def _persist_link(self, link: EvidenceLink) -> None:
        """Persist evidence link to storage."""
        # Extract tenant_id from evidence cache
        evidence = self._evidence_cache.get(link.evidence_id)
        tenant_id = evidence.tenant_id if evidence else None
        
        if not tenant_id:
            # Try to load evidence from storage to get tenant_id
            storage_evidence = self._load_evidence_from_storage(link.exception_id)
            for ev in storage_evidence:
                if ev.id == link.evidence_id:
                    tenant_id = ev.tenant_id
                    break
        
        if not tenant_id:
            # Can't determine tenant, skip persistence
            logger.warning(f"Cannot persist link {link.id}: tenant_id unknown")
            return
        
        evidence_file = self.storage_dir / f"{tenant_id}_{link.exception_id}_evidence.jsonl"
        
        try:
            with open(evidence_file, "a", encoding="utf-8") as f:
                link_dict = link.model_dump(by_alias=True, mode="json")
                link_dict["_type"] = "link"  # Mark as link for parsing
                f.write(json.dumps(link_dict, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist evidence link: {e}", exc_info=True)

    def _load_evidence_from_storage(
        self, exception_id: str, tenant_id: Optional[str] = None
    ) -> list[EvidenceItem]:
        """Load evidence items from storage."""
        evidence_items = []
        
        if tenant_id:
            # Load from specific tenant file
            evidence_file = self.storage_dir / f"{tenant_id}_{exception_id}_evidence.jsonl"
            if evidence_file.exists():
                evidence_items.extend(self._read_evidence_file(evidence_file))
        else:
            # Search all tenant files for this exception
            for evidence_file in self.storage_dir.glob(f"*_{exception_id}_evidence.jsonl"):
                evidence_items.extend(self._read_evidence_file(evidence_file))
        
        return evidence_items

    def _load_links_from_storage(
        self, exception_id: str, stage_name: Optional[str] = None
    ) -> list[EvidenceLink]:
        """Load evidence links from storage."""
        links = []
        
        # Search all tenant files for this exception
        for evidence_file in self.storage_dir.glob(f"*_{exception_id}_evidence.jsonl"):
            if evidence_file.exists():
                try:
                    with open(evidence_file, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                data = json.loads(line)
                                if data.get("_type") == "link":
                                    link = EvidenceLink.model_validate(data)
                                    if stage_name is None or link.stage_name == stage_name:
                                        links.append(link)
                            except Exception as e:
                                logger.warning(f"Failed to parse link: {e}")
                                continue
                except Exception as e:
                    logger.warning(f"Failed to read evidence file {evidence_file}: {e}")
        
        return links

    def _read_evidence_file(self, evidence_file: Path) -> list[EvidenceItem]:
        """Read evidence items from a file."""
        evidence_items = []
        
        if not evidence_file.exists():
            return evidence_items
        
        try:
            with open(evidence_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        # Skip links (marked with _type="link")
                        if data.get("_type") != "link":
                            evidence = EvidenceItem.model_validate(data)
                            evidence_items.append(evidence)
                    except Exception as e:
                        logger.warning(f"Failed to parse evidence item: {e}")
                        continue
        except Exception as e:
            logger.warning(f"Failed to read evidence file {evidence_file}: {e}")
        
        return evidence_items


# Global tracker instance
_evidence_tracker: Optional[EvidenceTracker] = None


def get_evidence_tracker() -> EvidenceTracker:
    """
    Get global evidence tracker instance.
    
    Returns:
        EvidenceTracker instance
    """
    global _evidence_tracker
    if _evidence_tracker is None:
        _evidence_tracker = EvidenceTracker()
    return _evidence_tracker


def record_evidence_item(
    evidence_type: EvidenceType,
    source_id: str,
    description: str,
    tenant_id: Optional[str] = None,
    exception_id: Optional[str] = None,
    similarity_score: Optional[float] = None,
    payload_ref: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> EvidenceItem:
    """
    Record an evidence item.
    
    Convenience function for integration.
    
    Args:
        evidence_type: Type of evidence
        source_id: Source identifier
        description: Human-readable description
        tenant_id: Optional tenant identifier
        exception_id: Optional exception identifier
        similarity_score: Optional similarity score
        payload_ref: Optional reference to full payload
        metadata: Optional additional metadata
        
    Returns:
        EvidenceItem instance
    """
    tracker = get_evidence_tracker()
    return tracker.record_evidence_item(
        evidence_type=evidence_type,
        source_id=source_id,
        description=description,
        tenant_id=tenant_id,
        exception_id=exception_id,
        similarity_score=similarity_score,
        payload_ref=payload_ref,
        metadata=metadata,
    )


def link_evidence_to_decision(
    exception_id: str,
    agent_name: str,
    stage_name: str,
    evidence_id: str,
    influence: EvidenceInfluence = EvidenceInfluence.SUPPORT,
    metadata: Optional[dict[str, Any]] = None,
) -> EvidenceLink:
    """
    Link an evidence item to an agent decision.
    
    Convenience function for integration.
    
    Args:
        exception_id: Exception identifier
        agent_name: Agent name
        stage_name: Pipeline stage name
        evidence_id: Evidence item identifier
        influence: How evidence influences the decision
        metadata: Optional additional metadata
        
    Returns:
        EvidenceLink instance
    """
    tracker = get_evidence_tracker()
    return tracker.link_evidence_to_decision(
        exception_id=exception_id,
        agent_name=agent_name,
        stage_name=stage_name,
        evidence_id=evidence_id,
        influence=influence,
        metadata=metadata,
    )


def get_evidence_for_exception(
    exception_id: str, tenant_id: Optional[str] = None
) -> list[EvidenceItem]:
    """
    Get all evidence items for an exception.
    
    Convenience function for integration.
    
    Args:
        exception_id: Exception identifier
        tenant_id: Optional tenant identifier
        
    Returns:
        List of EvidenceItem instances
    """
    tracker = get_evidence_tracker()
    return tracker.get_evidence_for_exception(exception_id, tenant_id)


def get_evidence_links_for_exception(
    exception_id: str, stage_name: Optional[str] = None
) -> list[EvidenceLink]:
    """
    Get all evidence links for an exception.
    
    Convenience function for integration.
    
    Args:
        exception_id: Exception identifier
        stage_name: Optional stage name filter
        
    Returns:
        List of EvidenceLink instances
    """
    tracker = get_evidence_tracker()
    return tracker.get_evidence_links_for_exception(exception_id, stage_name)

