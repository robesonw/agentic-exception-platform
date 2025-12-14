"""
Main demo data seeder for SentinAI platform.

Generates comprehensive demo data across all capabilities (Phases 4-8).
"""

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.demo.factories import DemoDataFactory
from src.demo.templates import (
    FINANCE_PLAYBOOK_NAMES,
    FINANCE_TOOL_NAMES,
    GLOBAL_TOOL_NAMES,
    HEALTHCARE_PLAYBOOK_NAMES,
    HEALTHCARE_TOOL_NAMES,
)
from src.infrastructure.db.models import (
    ActorType,
    ExceptionSeverity,
    ExceptionStatus,
    TenantStatus,
    ToolExecutionStatus,
)
from src.infrastructure.repositories.domain_pack_repository import DomainPackRepository
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.infrastructure.repositories.playbook_step_repository import PlaybookStepRepository
from src.infrastructure.repositories.tenant_policy_pack_repository import TenantPolicyPackRepository
from src.infrastructure.repositories.tenant_repository import TenantRepository
from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
from src.infrastructure.repositories.tool_execution_repository import ToolExecutionRepository
from src.repository.dto import (
    ExceptionCreateDTO,
    ExceptionEventCreateDTO,
    PlaybookCreateDTO,
    PlaybookStepCreateDTO,
    ToolDefinitionCreateDTO,
    ToolExecutionCreateDTO,
)
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository

logger = logging.getLogger(__name__)


class DemoDataSeeder:
    """Main seeder class for generating comprehensive demo data."""

    def __init__(self, session: AsyncSession, seed: int | None = None):
        """
        Initialize seeder.
        
        Args:
            session: Database session
            seed: Optional random seed for deterministic generation
        """
        self.session = session
        self.factory = DemoDataFactory(seed=seed)
        
        # Initialize repositories
        self.tenant_repo = TenantRepository(session)
        self.domain_pack_repo = DomainPackRepository(session)
        self.tenant_policy_repo = TenantPolicyPackRepository(session)
        self.exception_repo = ExceptionRepository(session)
        self.event_repo = ExceptionEventRepository(session)
        self.playbook_repo = PlaybookRepository(session)
        self.playbook_step_repo = PlaybookStepRepository(session)
        self.tool_def_repo = ToolDefinitionRepository(session)
        self.tool_enablement_repo = ToolEnablementRepository(session)
        self.tool_execution_repo = ToolExecutionRepository(session)

    async def reset_tenant_data(self, tenant_id: str) -> None:
        """
        Safely reset demo data for a tenant.
        
        Truncates tables in correct order to respect foreign key constraints.
        
        Args:
            tenant_id: Tenant identifier
        """
        logger.info(f"Resetting demo data for tenant: {tenant_id}")
        
        # Order matters due to foreign key constraints
        # Note: playbook_step doesn't have tenant_id directly, delete via playbook_id
        try:
            # Delete tool executions
            await self.session.execute(
                text('DELETE FROM tool_execution WHERE tenant_id = :tenant_id'),
                {"tenant_id": tenant_id},
            )
            
            # Delete tool enablements
            await self.session.execute(
                text('DELETE FROM tool_enablement WHERE tenant_id = :tenant_id'),
                {"tenant_id": tenant_id},
            )
            
            # Delete exception events
            await self.session.execute(
                text('DELETE FROM exception_event WHERE tenant_id = :tenant_id'),
                {"tenant_id": tenant_id},
            )
            
            # Delete exceptions
            await self.session.execute(
                text('DELETE FROM exception WHERE tenant_id = :tenant_id'),
                {"tenant_id": tenant_id},
            )
            
            # Delete playbook steps via playbook_id (playbook_step doesn't have tenant_id)
            await self.session.execute(
                text('''
                    DELETE FROM playbook_step 
                    WHERE playbook_id IN (
                        SELECT playbook_id FROM playbook WHERE tenant_id = :tenant_id
                    )
                '''),
                {"tenant_id": tenant_id},
            )
            
            # Delete playbooks
            await self.session.execute(
                text('DELETE FROM playbook WHERE tenant_id = :tenant_id'),
                {"tenant_id": tenant_id},
            )
            
            # Delete tool definitions (tenant-scoped only, global tools remain)
            await self.session.execute(
                text('DELETE FROM tool_definition WHERE tenant_id = :tenant_id'),
                {"tenant_id": tenant_id},
            )
            
            # Delete tenant policy packs
            await self.session.execute(
                text('DELETE FROM tenant_policy_pack_version WHERE tenant_id = :tenant_id'),
                {"tenant_id": tenant_id},
            )
            
            logger.debug(f"Deleted demo data for tenant {tenant_id}")
        except Exception as e:
            logger.warning(f"Error during reset for tenant {tenant_id}: {e}")
            # Rollback this transaction
            await self.session.rollback()
            raise
        
        await self.session.commit()
        logger.info(f"Reset complete for tenant: {tenant_id}")

    async def seed_tenant(self, tenant_id: str, tenant_name: str, domain: str) -> None:
        """
        Seed a tenant with all demo data.
        
        Args:
            tenant_id: Tenant identifier
            tenant_name: Tenant display name
            domain: Domain name (CapitalMarketsTrading or HealthcareClaimsAndCareOps)
        """
        logger.info(f"Seeding tenant: {tenant_id} ({tenant_name}) - Domain: {domain}")
        
        # Create tenant if not exists
        tenant = await self.tenant_repo.get_tenant(tenant_id)
        if not tenant:
            from src.infrastructure.db.models import Tenant
            tenant = Tenant(
                tenant_id=tenant_id,
                name=tenant_name,
                status=TenantStatus.ACTIVE,
            )
            self.session.add(tenant)
            await self.session.flush()
            logger.info(f"Created tenant: {tenant_id}")
        
        # Seed domain pack
        await self._seed_domain_pack(domain)
        
        # Seed tenant policy pack
        await self._seed_tenant_policy_pack(tenant_id, domain)
        
        # Seed playbooks
        await self._seed_playbooks(tenant_id, domain)
        
        # Seed tools
        await self._seed_tools(tenant_id, domain)
        
        await self.session.commit()
        logger.info(f"Completed seeding for tenant: {tenant_id}")

    async def _seed_domain_pack(self, domain: str) -> None:
        """Seed domain pack for the domain."""
        # Check if domain pack already exists
        existing = await self.domain_pack_repo.get_latest_domain_pack(domain)
        if existing:
            logger.info(f"Domain pack already exists for {domain}, skipping")
            return
        
        # Load domain pack from sample file
        domain_file_map = {
            "CapitalMarketsTrading": "finance.sample.json",
            "HealthcareClaimsAndCareOps": "healthcare.sample.json",
        }
        
        filename = domain_file_map.get(domain)
        if not filename:
            logger.warning(f"No domain pack file for {domain}, creating minimal pack")
            pack_json = {
                "domainName": domain,
                "entities": {},
                "exceptionTypes": {},
                "severityRules": [],
                "tools": {},
                "playbooks": [],
                "guardrails": {},
            }
        else:
            pack_path = Path(__file__).parent.parent.parent / "domainpacks" / filename
            if pack_path.exists():
                with open(pack_path) as f:
                    pack_json = json.load(f)
            else:
                logger.warning(f"Domain pack file not found: {pack_path}, creating minimal pack")
                pack_json = {"domainName": domain}
        
        await self.domain_pack_repo.create_domain_pack_version(domain, version=1, pack_json=pack_json)
        logger.info(f"Created domain pack for {domain}")

    async def _seed_tenant_policy_pack(self, tenant_id: str, domain: str) -> None:
        """Seed tenant policy pack."""
        existing = await self.tenant_policy_repo.get_latest_tenant_policy_pack(tenant_id)
        if existing:
            logger.info(f"Tenant policy pack already exists for {tenant_id}, skipping")
            return
        
        # Load tenant policy pack from sample file
        tenant_file_map = {
            "TENANT_FINANCE_001": "tenant_finance.sample.json",
            "TENANT_HEALTH_001": "tenant_healthcare.sample.json",
        }
        
        filename = tenant_file_map.get(tenant_id)
        if filename:
            pack_path = Path(__file__).parent.parent.parent / "tenantpacks" / filename
            if pack_path.exists():
                with open(pack_path) as f:
                    pack_json = json.load(f)
            else:
                pack_json = self._create_minimal_policy_pack(tenant_id, domain)
        else:
            pack_json = self._create_minimal_policy_pack(tenant_id, domain)
        
        await self.tenant_policy_repo.create_tenant_policy_pack_version(
            tenant_id, version=1, pack_json=pack_json
        )
        logger.info(f"Created tenant policy pack for {tenant_id}")

    def _create_minimal_policy_pack(self, tenant_id: str, domain: str) -> dict[str, Any]:
        """Create minimal tenant policy pack."""
        return {
            "tenantId": tenant_id,
            "domainName": domain,
            "customSeverityOverrides": [],
            "customGuardrails": {
                "allowLists": {"tools": [], "actions": []},
                "blockLists": {"tools": [], "actions": []},
                "humanApprovalThreshold": 0.75,
            },
            "approvedTools": [],
            "humanApprovalRules": [
                {"severity": "CRITICAL", "requireApproval": True},
                {"severity": "HIGH", "requireApproval": False},
            ],
            "retentionPolicies": {"dataTTL": 90},
            "customPlaybooks": [],
        }

    async def _seed_playbooks(self, tenant_id: str, domain: str) -> None:
        """Seed playbooks for tenant."""
        playbook_names = (
            FINANCE_PLAYBOOK_NAMES if domain == "CapitalMarketsTrading" else HEALTHCARE_PLAYBOOK_NAMES
        )
        
        exception_types = (
            self.factory.generate_exception_type(domain) for _ in range(len(playbook_names))
        )
        
        for i, (playbook_name, exception_type) in enumerate(zip(playbook_names, exception_types), 1):
            severity = self.factory.generate_severity(exception_type)
            conditions = self.factory.generate_playbook_conditions(domain, exception_type, severity)
            
            playbook_data = PlaybookCreateDTO(
                name=playbook_name,
                version=1,
                conditions=conditions,
            )
            
            playbook = await self.playbook_repo.create_playbook(tenant_id, playbook_data)
            
            # Create steps
            steps = self.factory.generate_playbook_steps(include_tool=True)
            for step_data in steps:
                step_dto = PlaybookStepCreateDTO(
                    name=step_data["name"],
                    action_type=step_data["action_type"],
                    params=step_data["params"],
                )
                await self.playbook_step_repo.create_step(playbook.playbook_id, step_dto, tenant_id)
            
            logger.debug(f"Created playbook: {playbook_name} with {len(steps)} steps")

    async def _seed_tools(self, tenant_id: str, domain: str) -> None:
        """Seed tools (global and tenant-scoped)."""
        # Seed global tools
        for tool_name in GLOBAL_TOOL_NAMES:
            tool_data = ToolDefinitionCreateDTO(
                name=tool_name,
                type="http",
                config=self.factory.generate_tool_config(tool_name, "http", is_global=True),
            )
            await self.tool_def_repo.create_tool(tenant_id=None, tool_data=tool_data)
        
        # Seed tenant-scoped tools
        tool_names = FINANCE_TOOL_NAMES if domain == "CapitalMarketsTrading" else HEALTHCARE_TOOL_NAMES
        
        for tool_name in tool_names[:3]:  # Create 3 tenant tools
            tool_data = ToolDefinitionCreateDTO(
                name=tool_name,
                type="http",
                config=self.factory.generate_tool_config(tool_name, "http", is_global=False),
            )
            tool = await self.tool_def_repo.create_tool(tenant_id=tenant_id, tool_data=tool_data)
            
            # Enable tool for tenant (default is enabled, but we set it explicitly)
            await self.tool_enablement_repo.set_enablement(tenant_id, tool.tool_id, enabled=True)
        
        # Add one dummy tool
        dummy_tool_data = ToolDefinitionCreateDTO(
            name="dummyTool",
            type="dummy",
            config=self.factory.generate_tool_config("dummyTool", "dummy", is_global=False),
        )
        dummy_tool = await self.tool_def_repo.create_tool(tenant_id=tenant_id, tool_data=dummy_tool_data)
        await self.tool_enablement_repo.set_enablement(tenant_id, dummy_tool.tool_id, enabled=True)
        
        logger.info(f"Created tools for tenant {tenant_id}")

    async def seed_exceptions(
        self, tenant_id: str, domain: str, count: int
    ) -> list[str]:
        """
        Seed exceptions with full event timelines.
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name
            count: Number of exceptions to create
            
        Returns:
            List of exception IDs created
        """
        logger.info(f"Seeding {count} exceptions for tenant {tenant_id}")
        
        exception_ids = []
        
        for i in range(count):
            exception_id = self.factory.generate_exception_id(tenant_id, i + 1)
            exception_ids.append(exception_id)
            
            exception_type = self.factory.generate_exception_type(domain)
            severity = self.factory.generate_severity(exception_type)
            status = self.factory.generate_status()
            created_at = self.factory.generate_created_at(days_back=7)
            sla_deadline = self.factory.generate_sla_deadline(created_at, severity)
            amount = self.factory.generate_amount(domain)
            entity = self.factory.generate_entity(domain)
            source_system = self.factory.generate_source_system(domain)
            owner = self.factory.generate_owner(status)
            
            # Get or create a playbook for this exception
            playbooks = await self.playbook_repo.list_playbooks(tenant_id)
            current_playbook_id = None
            current_step = None
            
            if playbooks and random.random() < 0.8:  # 80% have playbooks
                playbook = random.choice(playbooks)
                current_playbook_id = playbook.playbook_id
                # Get steps to determine max step
                steps = await self.playbook_step_repo.get_steps(playbook.playbook_id, tenant_id)
                max_step = len(steps) if steps else 3
                # Random step (1-3 for demo, or up to max if less)
                current_step = random.randint(1, min(3, max_step))
            
            exception_data = ExceptionCreateDTO(
                exception_id=exception_id,
                tenant_id=tenant_id,
                domain=domain,
                type=exception_type,
                severity=severity,
                status=status,
                source_system=source_system,
                entity=entity,
                amount=float(amount) if amount else None,
                sla_deadline=sla_deadline,
                owner=owner,
                current_playbook_id=current_playbook_id,
                current_step=current_step,
            )
            
            exception = await self.exception_repo.create_exception(tenant_id, exception_data)
            
            # Generate event timeline
            await self._seed_exception_timeline(tenant_id, exception_id, exception, created_at)
            
            if (i + 1) % 50 == 0:
                logger.info(f"Created {i + 1}/{count} exceptions")
        
        await self.session.commit()
        logger.info(f"Completed seeding {count} exceptions for tenant {tenant_id}")
        return exception_ids

    async def _seed_exception_timeline(
        self, tenant_id: str, exception_id: str, exception: Any, created_at: datetime
    ) -> None:
        """Generate realistic event timeline for an exception."""
        
        timeline_events = []
        current_time = created_at
        
        # ExceptionIngested
        actor_type, actor_id = self.factory.generate_actor("ExceptionIngested")
        event = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id=exception_id,
            tenant_id=tenant_id,
            event_type="ExceptionIngested",
            actor_type=actor_type,
            actor_id=actor_id,
            payload=self.factory.generate_event_payload("ExceptionIngested", exception_id),
        )
        timeline_events.append((current_time, event))
        current_time += timedelta(minutes=random.randint(1, 5))
        
        # ExceptionCreated
        actor_type, actor_id = self.factory.generate_actor("ExceptionCreated")
        event = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id=exception_id,
            tenant_id=tenant_id,
            event_type="ExceptionCreated",
            actor_type=actor_type,
            actor_id=actor_id,
            payload=self.factory.generate_event_payload("ExceptionCreated", exception_id),
        )
        timeline_events.append((current_time, event))
        current_time += timedelta(minutes=random.randint(2, 10))
        
        # TriageCompleted
        playbook_id = exception.current_playbook_id
        actor_type, actor_id = self.factory.generate_actor("TriageCompleted")
        event = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id=exception_id,
            tenant_id=tenant_id,
            event_type="TriageCompleted",
            actor_type=actor_type,
            actor_id=actor_id,
            payload=self.factory.generate_event_payload(
                "TriageCompleted", exception_id, playbook_id=playbook_id
            ),
        )
        timeline_events.append((current_time, event))
        current_time += timedelta(minutes=random.randint(5, 15))
        
        # PolicyEvaluated
        if playbook_id:
            actor_type, actor_id = self.factory.generate_actor("PolicyEvaluated")
            event = ExceptionEventCreateDTO(
                event_id=uuid4(),
                exception_id=exception_id,
                tenant_id=tenant_id,
                event_type="PolicyEvaluated",
                actor_type=actor_type,
                actor_id=actor_id,
                payload=self.factory.generate_event_payload(
                    "PolicyEvaluated", exception_id, playbook_id=playbook_id
                ),
            )
            timeline_events.append((current_time, event))
            current_time += timedelta(minutes=random.randint(3, 8))
            
            # PlaybookStarted
            actor_type, actor_id = self.factory.generate_actor("PlaybookStarted")
            event = ExceptionEventCreateDTO(
                event_id=uuid4(),
                exception_id=exception_id,
                tenant_id=tenant_id,
                event_type="PlaybookStarted",
                actor_type=actor_type,
                actor_id=actor_id,
                payload=self.factory.generate_event_payload("PlaybookStarted", exception_id),
            )
            timeline_events.append((current_time, event))
            current_time += timedelta(minutes=random.randint(2, 5))
            
            # PlaybookStepCompleted events
            if exception.current_step:
                steps = await self.playbook_step_repo.get_steps(playbook_id, tenant_id)
                for step in steps[:exception.current_step]:
                    actor_type, actor_id = self.factory.generate_actor("PlaybookStepCompleted")
                    event = ExceptionEventCreateDTO(
                        event_id=uuid4(),
                        exception_id=exception_id,
                        tenant_id=tenant_id,
                        event_type="PlaybookStepCompleted",
                        actor_type=actor_type,
                        actor_id=actor_id,
                        payload=self.factory.generate_event_payload(
                            "PlaybookStepCompleted",
                            exception_id,
                            step_order=step.step_order,
                            step_name=step.name,
                            action_type=step.action_type,
                        ),
                    )
                    timeline_events.append((current_time, event))
                    current_time += timedelta(minutes=random.randint(1, 5))
                    
                    # If step is call_tool, create tool execution
                    if step.action_type == "call_tool":
                        tool_name = step.params.get("tool_name", "unknown")
                        tools = await self.tool_def_repo.list_tools(tenant_id=tenant_id)
                        tool_def = next((t for t in tools if t.name == tool_name), None)
                        
                        if tool_def:
                            # ToolExecutionRequested
                            exec_id = uuid4()
                            actor_type, actor_id = self.factory.generate_actor("ToolExecutionRequested")
                            event = ExceptionEventCreateDTO(
                                event_id=uuid4(),
                                exception_id=exception_id,
                                tenant_id=tenant_id,
                                event_type="ToolExecutionRequested",
                                actor_type=actor_type,
                                actor_id=actor_id,
                                payload=self.factory.generate_event_payload(
                                    "ToolExecutionRequested",
                                    exception_id,
                                    tool_id=tool_def.tool_id,
                                    tool_name=tool_name,
                                ),
                            )
                            timeline_events.append((current_time, event))
                            current_time += timedelta(seconds=random.randint(1, 3))
                            
                            # Create tool execution record
                            success = random.random() < 0.9  # 90% success rate
                            exec_data = ToolExecutionCreateDTO(
                                tenant_id=tenant_id,
                                tool_id=tool_def.tool_id,
                                exception_id=exception_id,
                                status=ToolExecutionStatus.SUCCEEDED if success else ToolExecutionStatus.FAILED,
                                requested_by_actor_type=actor_type,
                                requested_by_actor_id=actor_id,
                                input_payload=self.factory.generate_tool_execution_input(tool_name),
                                output_payload=self.factory.generate_tool_execution_output(success),
                                error_message=None if success else "Demo error message",
                            )
                            await self.tool_execution_repo.create_execution(exec_data)
                            
                            # ToolExecutionCompleted/Failed
                            event_type = "ToolExecutionCompleted" if success else "ToolExecutionFailed"
                            actor_type, actor_id = self.factory.generate_actor(event_type)
                            event = ExceptionEventCreateDTO(
                                event_id=uuid4(),
                                exception_id=exception_id,
                                tenant_id=tenant_id,
                                event_type=event_type,
                                actor_type=actor_type,
                                actor_id=actor_id,
                                payload=self.factory.generate_event_payload(
                                    event_type,
                                    exception_id,
                                    tool_id=tool_def.tool_id,
                                    tool_name=tool_name,
                                ),
                            )
                            timeline_events.append((current_time, event))
                            current_time += timedelta(seconds=random.randint(1, 2))
        
        # ResolutionSuggested
        if exception.status == ExceptionStatus.RESOLVED:
            actor_type, actor_id = self.factory.generate_actor("ResolutionSuggested")
            event = ExceptionEventCreateDTO(
                event_id=uuid4(),
                exception_id=exception_id,
                tenant_id=tenant_id,
                event_type="ResolutionSuggested",
                actor_type=actor_type,
                actor_id=actor_id,
                payload=self.factory.generate_event_payload("ResolutionSuggested", exception_id),
            )
            timeline_events.append((current_time, event))
            current_time += timedelta(minutes=random.randint(1, 3))
            
            # PlaybookCompleted
            if playbook_id:
                actor_type, actor_id = self.factory.generate_actor("PlaybookCompleted")
                event = ExceptionEventCreateDTO(
                    event_id=uuid4(),
                    exception_id=exception_id,
                    tenant_id=tenant_id,
                    event_type="PlaybookCompleted",
                    actor_type=actor_type,
                    actor_id=actor_id,
                    payload=self.factory.generate_event_payload("PlaybookCompleted", exception_id),
                )
                timeline_events.append((current_time, event))
                current_time += timedelta(minutes=random.randint(1, 2))
            
            # FeedbackCaptured
            actor_type, actor_id = self.factory.generate_actor("FeedbackCaptured")
            event = ExceptionEventCreateDTO(
                event_id=uuid4(),
                exception_id=exception_id,
                tenant_id=tenant_id,
                event_type="FeedbackCaptured",
                actor_type=actor_type,
                actor_id=actor_id,
                payload=self.factory.generate_event_payload("FeedbackCaptured", exception_id, feedback="positive"),
            )
            timeline_events.append((current_time, event))
        
        # Insert all events
        for event_time, event in timeline_events:
            # Set created_at to event_time (we'll need to update after insert)
            await self.event_repo.append_event(tenant_id, event)
        
        logger.debug(f"Created {len(timeline_events)} events for exception {exception_id}")

