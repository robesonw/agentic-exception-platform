"""
Demo Scenario Engine - Generates exceptions based on scenario configurations.

Supports three execution modes:
- Burst: Generate N exceptions immediately
- Scheduled: Generate exceptions at intervals for a duration
- Continuous: Generate exceptions continuously until stopped
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.demo.catalog_loader import DemoCatalogLoader
from src.demo.catalog_types import (
    DemoCatalog,
    DemoScenario,
    DemoTenant,
    Industry,
    WeightedChoice,
)
from src.infrastructure.db.models import (
    DemoRun,
    DemoRunMode,
    DemoRunStatus,
    ExceptionSeverity,
    ExceptionStatus,
)
from src.infrastructure.repositories.demo_run_repository import (
    DemoRunConflictError,
    DemoRunRepository,
)
from src.infrastructure.repositories.platform_settings_repository import PlatformSettingsRepository
from src.infrastructure.repositories.tenant_repository import TenantRepository
from src.repository.dto import ExceptionCreateDTO, ExceptionEventCreateDTO
from src.repository.exceptions_repository import ExceptionRepository
from src.repository.exception_events_repository import ExceptionEventRepository

logger = logging.getLogger(__name__)


class DemoScenarioEngine:
    """
    Engine for executing demo scenarios.
    
    Manages scenario runs with overlap prevention and supports
    burst, scheduled, and continuous modes.
    """
    
    # Class-level state for background task
    _background_task: Optional[asyncio.Task] = None
    _stop_event: Optional[asyncio.Event] = None
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
        # Initialize repositories
        self.settings_repo = PlatformSettingsRepository(session)
        self.run_repo = DemoRunRepository(session)
        self.tenant_repo = TenantRepository(session)
        self.exception_repo = ExceptionRepository(session)
        self.event_repo = ExceptionEventRepository(session)
        
        # Always start with no catalog cache to ensure fresh load
        self._catalog: Optional[DemoCatalog] = None
        # Clear class-level cache to ensure fresh catalog
        DemoCatalogLoader.clear_cache()
    
    async def get_status(self) -> dict[str, Any]:
        """
        Get current demo engine status.
        
        Returns:
            Status dict with enabled, active run, counts, etc.
        """
        enabled = await self.settings_repo.get_value("demo.enabled", False)
        bootstrap_last = await self.settings_repo.get_value("demo.bootstrap.lastAt")
        scenarios_active = await self.settings_repo.get_value("demo.scenarios.active", [])
        
        # Get active run
        active_run = await self.run_repo.get_active_run()
        active_run_dict = self.run_repo.run_to_dict(active_run) if active_run else None
        
        # Count demo entities
        tenant_count = await self._count_demo_tenants()
        exception_count = await self._count_demo_exceptions()
        
        # Get available scenarios from catalog
        scenarios_available = []
        try:
            catalog = self._get_catalog()
            scenarios_available = [s.scenario_id for s in catalog.scenarios]
        except Exception:
            pass
        
        return {
            "enabled": enabled,
            "bootstrap_complete": bootstrap_last is not None,
            "bootstrap_last_at": bootstrap_last.isoformat() if bootstrap_last else None,
            "tenant_count": tenant_count,
            "exception_count": exception_count,
            "playbook_count": 0,  # TODO: count demo playbooks
            "tool_count": 0,  # TODO: count demo tools
            "scenarios_available": scenarios_available,
            "scenarios_active": scenarios_active,
            "active_run": active_run_dict,
        }
    
    async def start_burst_run(
        self,
        scenario_ids: list[str],
        tenant_keys: list[str],
        burst_count: int = 25,
        created_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Start a burst run that generates exceptions immediately.
        
        Args:
            scenario_ids: List of scenario IDs to run
            tenant_keys: Target tenant keys (empty = all demo tenants)
            burst_count: Number of exceptions to generate
            created_by: User/system starting the run
            
        Returns:
            Run result dict
            
        Raises:
            DemoRunConflictError: If another run is active
        """
        # Create and start run
        run = await self.run_repo.create_run(
            mode=DemoRunMode.BURST,
            scenario_ids=scenario_ids,
            tenant_keys=tenant_keys,
            burst_count=burst_count,
            created_by=created_by,
        )
        
        run = await self.run_repo.start_run(run.run_id)
        
        try:
            # Generate all exceptions immediately
            generated = await self._generate_exceptions(
                run=run,
                count=burst_count,
                scenario_ids=scenario_ids,
                tenant_keys=tenant_keys,
            )
            
            # Update count and complete
            await self.run_repo.update_progress(run.run_id, generated_count=generated)
            run = await self.run_repo.complete_run(run.run_id, DemoRunStatus.COMPLETED)
            
            await self.session.commit()
            
            logger.info(f"Burst run completed: {generated} exceptions generated")
            
            return self.run_repo.run_to_dict(run)
            
        except Exception as e:
            await self.run_repo.complete_run(run.run_id, DemoRunStatus.FAILED, str(e))
            await self.session.commit()
            raise
    
    async def start_scheduled_run(
        self,
        scenario_ids: list[str],
        tenant_keys: list[str],
        frequency_seconds: int = 2,
        duration_seconds: int = 120,
        intensity_multiplier: float = 1.0,
        created_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Start a scheduled run that generates exceptions for a duration.
        
        Args:
            scenario_ids: List of scenario IDs to run
            tenant_keys: Target tenant keys (empty = all demo tenants)
            frequency_seconds: Generation interval
            duration_seconds: Total duration
            intensity_multiplier: Number of exceptions per tick
            created_by: User/system starting the run
            
        Returns:
            Run info dict (run starts in background)
            
        Raises:
            DemoRunConflictError: If another run is active
        """
        # Create run
        run = await self.run_repo.create_run(
            mode=DemoRunMode.SCHEDULED,
            scenario_ids=scenario_ids,
            tenant_keys=tenant_keys,
            frequency_seconds=frequency_seconds,
            duration_seconds=duration_seconds,
            intensity_multiplier=intensity_multiplier,
            created_by=created_by,
        )
        
        run = await self.run_repo.start_run(run.run_id)
        await self.session.commit()
        
        # Start background task
        self._start_background_runner(run.run_id)
        
        logger.info(
            f"Scheduled run started: {run.run_id}, "
            f"frequency={frequency_seconds}s, duration={duration_seconds}s"
        )
        
        return self.run_repo.run_to_dict(run)
    
    async def start_continuous_run(
        self,
        scenario_ids: list[str],
        tenant_keys: list[str],
        frequency_seconds: int = 120,
        intensity_multiplier: float = 1.0,
        created_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Start a continuous run that generates exceptions until stopped.
        
        Args:
            scenario_ids: List of scenario IDs to run
            tenant_keys: Target tenant keys (empty = all demo tenants)
            frequency_seconds: Generation interval
            intensity_multiplier: Number of exceptions per tick
            created_by: User/system starting the run
            
        Returns:
            Run info dict (run starts in background)
            
        Raises:
            DemoRunConflictError: If another run is active
        """
        # Create run
        run = await self.run_repo.create_run(
            mode=DemoRunMode.CONTINUOUS,
            scenario_ids=scenario_ids,
            tenant_keys=tenant_keys,
            frequency_seconds=frequency_seconds,
            intensity_multiplier=intensity_multiplier,
            created_by=created_by,
        )
        
        run = await self.run_repo.start_run(run.run_id)
        await self.session.commit()
        
        # Start background task
        self._start_background_runner(run.run_id)
        
        logger.info(f"Continuous run started: {run.run_id}, frequency={frequency_seconds}s")
        
        return self.run_repo.run_to_dict(run)
    
    async def stop_run(self) -> Optional[dict[str, Any]]:
        """
        Stop the currently active run.
        
        Returns:
            Stopped run info or None if no active run
        """
        # Signal stop
        if self._stop_event:
            self._stop_event.set()
        
        # Stop in DB
        run = await self.run_repo.stop_active_run()
        
        if run:
            await self.session.commit()
            logger.info(f"Stopped run: {run.run_id}")
            return self.run_repo.run_to_dict(run)
        
        return None
    
    def _start_background_runner(self, run_id: UUID) -> None:
        """Start background task for scheduled/continuous runs."""
        # Cancel existing task if any
        if self._background_task and not self._background_task.done():
            self._stop_event.set()
            self._background_task.cancel()
        
        # Create new stop event
        self._stop_event = asyncio.Event()
        
        # Start new task
        self._background_task = asyncio.create_task(
            self._run_background_loop(run_id)
        )
    
    async def _run_background_loop(self, run_id: UUID) -> None:
        """Background loop for scheduled/continuous runs."""
        try:
            while not self._stop_event.is_set():
                # Create new session for each iteration
                from src.infrastructure.db.session import get_session_factory
                
                async with get_session_factory()() as session:
                    run_repo = DemoRunRepository(session)
                    
                    # Get current run state
                    run = await run_repo.get_by_id(run_id)
                    
                    if not run or run.status != DemoRunStatus.RUNNING:
                        logger.info(f"Run {run_id} is no longer running, stopping loop")
                        break
                    
                    # Check scheduled expiry
                    if run.mode == DemoRunMode.SCHEDULED:
                        expired = await run_repo.check_scheduled_expiry(run_id)
                        if expired:
                            await session.commit()
                            logger.info(f"Scheduled run {run_id} expired")
                            break
                    
                    # Generate exceptions for this tick
                    exception_repo = ExceptionRepository(session)
                    event_repo = ExceptionEventRepository(session)
                    
                    intensity = run.intensity_multiplier or 1.0
                    count = max(1, int(intensity))
                    
                    generated = await self._generate_exceptions_in_session(
                        session=session,
                        run=run,
                        count=count,
                        scenario_ids=run.scenario_ids or [],
                        tenant_keys=run.tenant_keys or [],
                    )
                    
                    # Update progress
                    await run_repo.update_progress(run_id, increment_count=generated)
                    await session.commit()
                    
                    logger.debug(f"Generated {generated} exceptions for run {run_id}")
                
                # Wait for next tick
                frequency = run.frequency_seconds or 60
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=frequency,
                    )
                    # If we get here, stop was requested
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue loop
                    pass
                    
        except asyncio.CancelledError:
            logger.info(f"Background loop for run {run_id} cancelled")
        except Exception as e:
            logger.error(f"Background loop error for run {run_id}: {e}", exc_info=True)
            # Mark run as failed
            from src.infrastructure.db.session import get_session_factory
            async with get_session_factory()() as session:
                run_repo = DemoRunRepository(session)
                await run_repo.complete_run(run_id, DemoRunStatus.FAILED, str(e))
                await session.commit()
    
    async def _generate_exceptions(
        self,
        run: DemoRun,
        count: int,
        scenario_ids: list[str],
        tenant_keys: list[str],
    ) -> int:
        """Generate exceptions using current session."""
        return await self._generate_exceptions_in_session(
            session=self.session,
            run=run,
            count=count,
            scenario_ids=scenario_ids,
            tenant_keys=tenant_keys,
        )
    
    async def _generate_exceptions_in_session(
        self,
        session: AsyncSession,
        run: DemoRun,
        count: int,
        scenario_ids: list[str],
        tenant_keys: list[str],
    ) -> int:
        """Generate exceptions using provided session."""
        exception_repo = ExceptionRepository(session)
        event_repo = ExceptionEventRepository(session)
        tenant_repo = TenantRepository(session)
        
        # Get catalog
        catalog = self._get_catalog()
        
        # Get scenarios
        scenarios = [
            s for s in catalog.scenarios
            if not scenario_ids or s.scenario_id in scenario_ids
        ]
        
        if not scenarios:
            logger.warning("No scenarios found for generation")
            return 0
        
        # Get target tenants
        demo_tenants = await self._get_demo_tenants(tenant_repo, tenant_keys)
        
        if not demo_tenants:
            logger.warning("No demo tenants found for generation")
            return 0
        
        generated = 0
        
        for i in range(count):
            # Pick random scenario and tenant
            scenario = random.choice(scenarios)
            tenant = random.choice([t for t in demo_tenants if t.industry == scenario.industry.value])
            
            if not tenant:
                # Fall back to any tenant
                tenant = random.choice(demo_tenants)
            
            # Generate exception (publishes to Kafka, intake worker will create in DB)
            await self._create_exception_from_scenario(
                exception_repo=exception_repo,
                event_repo=event_repo,
                scenario=scenario,
                tenant_id=tenant.tenant_id,
            )
            # Always count as generated if no exception was raised
            generated += 1
        
        return generated
    
    async def _create_exception_from_scenario(
        self,
        exception_repo: ExceptionRepository,
        event_repo: ExceptionEventRepository,
        scenario: DemoScenario,
        tenant_id: str,
    ) -> Optional[Any]:
        """Create a single exception from scenario and publish ExceptionIngested event for processing."""
        try:
            # Select exception type based on weights
            exc_type = self._weighted_choice(scenario.weights.exception_types)
            # Normalize exception type: strip any leading colon(s) and whitespace, then uppercase if all lowercase
            # Handles cases like: ":fin_settlement_fail", ": fin_settlement_fail", "fin_settlement_fail"
            if exc_type:
                original_exc_type = exc_type  # For logging
                # Strip ALL leading colons (handles ":value", "::value", etc.)
                while exc_type.startswith(':'):
                    exc_type = exc_type[1:]
                # Strip leading/trailing whitespace
                exc_type = exc_type.strip()
                # Convert to uppercase if it's all lowercase (preserve mixed case like "FIN_SETTLEMENT_FAIL")
                if exc_type and exc_type.islower():
                    exc_type = exc_type.upper()
                # Log normalization for debugging
                if original_exc_type != exc_type:
                    logger.info(
                        f"Normalized exception type: {repr(original_exc_type)} -> {repr(exc_type)} "
                        f"(scenario={scenario.scenario_id})"
                    )
            severity = self._weighted_choice(scenario.weights.severities)
            source = self._weighted_choice(scenario.weights.sources) if scenario.weights.sources else "DemoSystem"
            
            # Map severity string to enum
            severity_map = {
                "low": ExceptionSeverity.LOW,
                "medium": ExceptionSeverity.MEDIUM,
                "high": ExceptionSeverity.HIGH,
                "critical": ExceptionSeverity.CRITICAL,
            }
            severity_enum = severity_map.get(severity.lower(), ExceptionSeverity.MEDIUM)
            
            # Generate IDs
            now = datetime.now(timezone.utc)
            exc_id = f"EXC-{scenario.industry.value[:3].upper()}-{now.strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
            
            # Generate correlated entity data
            entity = self._generate_entity_id(scenario.industry)
            amount = Decimal(str(round(random.uniform(1000, 500000), 2)))
            
            # FINAL normalization before putting in raw_payload - strip ANY colons that might have slipped through
            if exc_type:
                while exc_type.startswith(':'):
                    exc_type = exc_type[1:]
                exc_type = exc_type.strip()
                if ":" in exc_type:
                    exc_type = exc_type.replace(":", "").strip()
                if exc_type and exc_type.islower():
                    exc_type = exc_type.upper()
            
            # Build raw payload for ExceptionIngested event
            raw_payload = {
                "exceptionType": exc_type,
                "tenantId": tenant_id,
                "sourceSystem": source,
                "domain": self._industry_to_domain(scenario.industry),
                "entity": entity,
                "amount": float(amount),
                "severity": severity.lower(),
                "timestamp": now.isoformat(),
                "scenario_id": scenario.scenario_id,
                "demo": True,
            }
            
            # Publish ExceptionIngested event to trigger worker processing
            # This ensures the intake worker processes the exception through the pipeline
            try:
                from src.events.types import ExceptionIngested
                from src.messaging.event_publisher import EventPublisherService
                from src.messaging.kafka_broker import KafkaBroker
                from src.messaging.settings import get_broker_settings
                from src.messaging.event_store import DatabaseEventStore
                
                # Create event publisher (use DatabaseEventStore with current session)
                broker_settings = get_broker_settings()
                broker = KafkaBroker(settings=broker_settings)
                event_store = DatabaseEventStore(session=self.session)
                event_publisher = EventPublisherService(broker=broker, event_store=event_store)
                
                # Phase 9 P9-24: Redact PII before publishing
                from src.security.pii_redaction import get_pii_redaction_service
                pii_service = get_pii_redaction_service()
                redacted_payload, redaction_metadata = pii_service.redact_pii(
                    data=raw_payload,
                    tenant_id=tenant_id,
                )
                redacted_payload = pii_service.ensure_secrets_never_logged(redacted_payload, tenant_id)
                
                # Create and publish ExceptionIngested event
                exception_ingested_event = ExceptionIngested.create(
                    tenant_id=tenant_id,
                    exception_id=exc_id,
                    raw_payload=redacted_payload,
                    source_system=source,
                    ingestion_method="demo",
                    correlation_id=exc_id,
                    metadata={
                        "redaction_metadata": redaction_metadata,
                        "scenario_id": scenario.scenario_id,
                        "demo": True,
                    },
                )
                
                await event_publisher.publish_event(
                    topic="exceptions",
                    event=exception_ingested_event.model_dump(by_alias=True),
                )
                
                logger.info(
                    f"Published ExceptionIngested event for demo exception: exception_id={exc_id}, "
                    f"tenant_id={tenant_id}, scenario_id={scenario.scenario_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to publish ExceptionIngested event for exception {exc_id}: {e}",
                    exc_info=True,
                )
                # Continue even if event publishing fails - exception is still created
                # but won't be processed by workers
            
            # Do NOT create exception directly in DB - let the intake worker create it
            # This ensures:
            # 1. No duplication (exception created once, via intake worker)
            # 2. Consistent normalization (intake worker normalizes exception type)
            # 3. Proper pipeline processing (exception goes through full pipeline)
            # The intake worker will create the exception in DB when processing the ExceptionIngested event
            # No need to create initial event - the intake worker will create ExceptionIngested event
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating exception from scenario: {e}", exc_info=True)
            return None
    
    def _weighted_choice(self, choices: list[WeightedChoice]) -> str:
        """Select a value based on weights."""
        if not choices:
            return ""

        values = [c.value for c in choices]
        weights = [c.weight for c in choices]

        selected = random.choices(values, weights=weights, k=1)[0]
        
        # AGGRESSIVE normalization: strip ANY leading colons, spaces, and normalize case
        # This ensures we NEVER return a value with colon prefix
        if selected:
            # Strip ALL leading colons (handles ":value", "::value", ": value", etc.)
            while selected.startswith(':') or selected.startswith(' :'):
                selected = selected.lstrip(':').lstrip(' ')
            # Strip leading/trailing whitespace
            selected = selected.strip()
            # Convert to uppercase if all lowercase
            if selected and selected.islower():
                selected = selected.upper()
        
        return selected
    
    def _generate_entity_id(self, industry: Industry) -> str:
        """Generate entity ID based on industry."""
        prefixes = {
            Industry.FINANCE: "TRD",
            Industry.HEALTHCARE: "PAT",
            Industry.INSURANCE: "POL",
            Industry.RETAIL: "ORD",
            Industry.SAAS_OPS: "INC",
        }
        prefix = prefixes.get(industry, "ENT")
        return f"{prefix}-{datetime.now().strftime('%Y')}-{random.randint(100000, 999999)}"
    
    def _industry_to_domain(self, industry: Industry) -> str:
        """Map industry to domain name."""
        domain_map = {
            Industry.FINANCE: "CapitalMarketsTrading",
            Industry.HEALTHCARE: "HealthcareClaimsAndCareOps",
            Industry.INSURANCE: "InsuranceClaimsProcessing",
            Industry.RETAIL: "RetailOperations",
            Industry.SAAS_OPS: "SaaSOperations",
        }
        return domain_map.get(industry, "Unknown")
    
    def _get_catalog(self) -> DemoCatalog:
        """Get or load demo catalog."""
        if self._catalog is None:
            # Force reload to ensure we get fresh catalog (clears any stale cache)
            DemoCatalogLoader.clear_cache()
            self._catalog = DemoCatalogLoader.load(force_reload=True)
        return self._catalog
    
    async def _count_demo_tenants(self) -> int:
        """Count demo tenants."""
        from sqlalchemy import select, func
        from src.infrastructure.db.models import Tenant
        
        result = await self.session.execute(
            select(func.count()).select_from(Tenant).where(
                Tenant.tags.contains(["demo"])
            )
        )
        return result.scalar() or 0
    
    async def _count_demo_exceptions(self) -> int:
        """Count demo exceptions (from demo tenants)."""
        from sqlalchemy import select, func
        from src.infrastructure.db.models import Exception as ExcModel, Tenant
        
        # Get demo tenant IDs
        result = await self.session.execute(
            select(Tenant.tenant_id).where(
                Tenant.tags.contains(["demo"])
            )
        )
        demo_tenant_ids = [r[0] for r in result.fetchall()]
        
        if not demo_tenant_ids:
            return 0
        
        result = await self.session.execute(
            select(func.count()).select_from(ExcModel).where(
                ExcModel.tenant_id.in_(demo_tenant_ids)
            )
        )
        return result.scalar() or 0
    
    async def _get_demo_tenants(
        self,
        tenant_repo: TenantRepository,
        tenant_keys: list[str],
    ) -> list:
        """Get demo tenants, optionally filtered by keys."""
        from sqlalchemy import select
        from src.infrastructure.db.models import Tenant
        
        query = select(Tenant).where(Tenant.tags.contains(["demo"]))
        
        if tenant_keys:
            query = query.where(Tenant.tenant_id.in_(tenant_keys))
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
