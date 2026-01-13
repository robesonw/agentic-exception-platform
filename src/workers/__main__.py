"""
Worker entry point for Phase 9.

Provides command-line interface for running workers with environment-driven configuration.

Phase 9 P9-26: Worker Scaling Configuration.
Reference: docs/phase9-async-scale-mvp.md Section 9

Usage:
    python -m src.workers --worker-type intake --concurrency 4 --group-id intake-workers-1
    # Or use environment variables:
    WORKER_TYPE=intake CONCURRENCY=4 GROUP_ID=intake-workers-1 python -m src.workers
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Any, Optional

from src.infrastructure.db.session import initialize_database
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging import get_broker
from src.workers.base import AgentWorker
from src.workers.config import WorkerConfig, get_worker_class_name
from src.workers.health_server import WorkerHealthServer, get_worker_port
from src.workers.intake_worker import IntakeWorker
from src.workers.triage_worker import TriageWorker
from src.workers.policy_worker import PolicyWorker
from src.workers.playbook_worker import PlaybookWorker
from src.workers.tool_worker import ToolWorker
from src.workers.feedback_worker import FeedbackWorker
from src.workers.sla_monitor_worker import SLAMonitorWorker

logger = logging.getLogger(__name__)

# Worker class mapping
WORKER_CLASSES = {
    "intake": IntakeWorker,
    "triage": TriageWorker,
    "policy": PolicyWorker,
    "playbook": PlaybookWorker,
    "tool": ToolWorker,
    "feedback": FeedbackWorker,
    "sla_monitor": SLAMonitorWorker,
}


def create_worker(config: WorkerConfig) -> AgentWorker:
    """
    Create worker instance from configuration.
    
    Phase 9 P9-26: Factory function to create workers based on WORKER_TYPE.
    
    Args:
        config: WorkerConfig instance
        
    Returns:
        AgentWorker instance
        
    Raises:
        ValueError: If worker type is not supported
    """
    worker_class = WORKER_CLASSES.get(config.worker_type.lower())
    if not worker_class:
        raise ValueError(
            f"Unsupported worker type: {config.worker_type}. "
            f"Supported types: {', '.join(WORKER_CLASSES.keys())}"
        )
    
    # Get broker
    broker = get_broker()
    
    # Get topics for worker type
    topics = _get_topics_for_worker_type(config.worker_type)
    
    # Create event processing repository (for idempotency)
    # Note: This requires a database session, which we'll create per-worker
    # For MVP, we'll pass None and let workers handle it internally
    event_processing_repo = None
    
    # Create common dependencies for all workers
    from src.messaging.settings import get_broker_settings
    from src.messaging.kafka_broker import KafkaBroker
    from src.messaging.event_store import EventStore
    from src.messaging.event_publisher import EventPublisherService
    
    broker_settings = get_broker_settings()
    kafka_broker = KafkaBroker(settings=broker_settings)
    
    # Create a DatabaseEventStore wrapper that creates sessions per-operation
    # This allows workers to persist events to the database without holding a session
    class PerOperationDatabaseEventStore(EventStore):
        """DatabaseEventStore wrapper that creates sessions per-operation."""
        
        async def store_event(
            self,
            event_id: str,
            event_type: str,
            tenant_id: str,
            exception_id: Optional[str],
            timestamp: datetime,
            correlation_id: Optional[str],
            payload: dict[str, Any],
            metadata: Optional[dict[str, Any]] = None,
            version: int = 1,
        ) -> None:
            """Store event in database using a session per-operation."""
            from src.infrastructure.db.session import get_db_session_context
            from src.messaging.event_store import DatabaseEventStore
            
            async with get_db_session_context() as session:
                db_event_store = DatabaseEventStore(session=session)
                await db_event_store.store_event(
                    event_id=event_id,
                    event_type=event_type,
                    tenant_id=tenant_id,
                    exception_id=exception_id,
                    timestamp=timestamp,
                    correlation_id=correlation_id,
                    payload=payload,
                    metadata=metadata,
                    version=version,
                )
        
        async def get_event(self, event_id: str) -> Optional[dict[str, Any]]:
            """Retrieve event from database (requires tenant context - not implemented for workers)."""
            return None
    
    event_store = PerOperationDatabaseEventStore()
    # Disable rate limiting for MVP/testing
    event_publisher = EventPublisherService(
        broker=kafka_broker, 
        event_store=event_store,
        enable_rate_limiting=False  # Disabled for MVP
    )
    
    # Create worker-specific dependencies
    if config.worker_type.lower() == "intake":
        # IntakeWorker doesn't need exception_repository (creates per-operation)
        exception_repository = None
        
        worker = worker_class(
            broker=broker,
            topics=topics,
            group_id=config.group_id,
            event_publisher=event_publisher,
            exception_repository=exception_repository,
            event_processing_repo=event_processing_repo,
        )
    elif config.worker_type.lower() in ["policy", "triage", "playbook"]:
        # These workers need domain_pack and tenant_policy
        # For MVP, create minimal stubs - workers will load packs per-event
        from src.models.domain_pack import DomainPack
        from src.models.tenant_policy import TenantPolicyPack
        from src.repository.exceptions_repository import ExceptionRepository
        
        # Create minimal domain pack stub (workers should load real packs per-event)
        domain_pack = DomainPack(
            domain_name="stub",
        )
        
        # Create minimal tenant policy stub
        tenant_policy = TenantPolicyPack(
            tenant_id="stub",
            domain_name="stub",
        )
        
        exception_repository = None  # Workers will create per-operation
        
        if config.worker_type.lower() == "policy":
            worker = worker_class(
                broker=broker,
                topics=topics,
                group_id=config.group_id,
                event_publisher=event_publisher,
                exception_repository=exception_repository,
                domain_pack=domain_pack,
                tenant_policy=tenant_policy,
                event_processing_repo=event_processing_repo,
            )
        elif config.worker_type.lower() == "triage":
            worker = worker_class(
                broker=broker,
                topics=topics,
                group_id=config.group_id,
                event_publisher=event_publisher,
                exception_repository=exception_repository,
                domain_pack=domain_pack,
                tenant_policy=tenant_policy,
                event_processing_repo=event_processing_repo,
            )
        elif config.worker_type.lower() == "playbook":
            worker = worker_class(
                broker=broker,
                topics=topics,
                group_id=config.group_id,
                event_publisher=event_publisher,
                exception_repository=exception_repository,
                domain_pack=domain_pack,
                tenant_policy=tenant_policy,
                event_processing_repo=event_processing_repo,
            )
    elif config.worker_type.lower() == "tool":
        # ToolWorker creates ToolExecutionService per-operation with session-based repositories
        # Pass None - worker will create service per-operation in process_event
        worker = worker_class(
            broker=broker,
            topics=topics,
            group_id=config.group_id,
            event_publisher=event_publisher,
            tool_execution_service=None,  # Created per-operation in process_event
            event_processing_repo=event_processing_repo,
        )
    elif config.worker_type.lower() == "feedback":
        # FeedbackWorker needs event_publisher and exception_repository
        from src.repository.exceptions_repository import ExceptionRepository
        exception_repository = None  # Workers will create per-operation
        
        worker = worker_class(
            broker=broker,
            topics=topics,
            group_id=config.group_id,
            event_publisher=event_publisher,
            exception_repository=exception_repository,
            event_processing_repo=event_processing_repo,
        )
    elif config.worker_type.lower() == "sla_monitor":
        # SLA monitor has different constructor
        worker = worker_class(
            event_publisher=event_publisher,
            check_interval_seconds=60,
        )
    else:
        # Fallback for unknown worker types
        logger.warning(f"Unknown worker type {config.worker_type}, using minimal constructor")
        worker = worker_class(
            broker=broker,
            topics=topics,
            group_id=config.group_id,
            event_processing_repo=event_processing_repo,
        )
    
    if worker is None:
        return None
    
    logger.info(
        f"Created {config.worker_type} worker: topics={topics}, "
        f"group_id={config.group_id}, concurrency={config.concurrency}"
    )
    
    return worker


def _get_topics_for_worker_type(worker_type: str) -> list[str]:
    """
    Get topic names for a worker type.
    
    Args:
        worker_type: Worker type (e.g., "intake", "triage")
        
    Returns:
        List of topic names
    """
    # Phase 9 P9-23: Option A (MVP) - Shared topics
    # Each worker type subscribes to relevant topics
    topic_mapping = {
        "intake": ["exceptions"],
        "triage": ["exceptions"],
        "policy": ["exceptions"],
        "playbook": ["exceptions"],
        "tool": ["exceptions"],
        "feedback": ["exceptions"],
        "sla_monitor": ["sla"],
    }
    
    topics = topic_mapping.get(worker_type.lower(), ["exceptions"])
    return topics


def setup_logging() -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """
    Main entry point for worker.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    setup_logging()
    
    try:
        # Load configuration from environment
        config = WorkerConfig.from_env()
        logger.info(f"Starting worker with configuration: {config}")
        
        # Initialize database connection
        logger.info("Initializing database connection...")
        db_initialized = asyncio.run(initialize_database())
        if not db_initialized:
            logger.error("Failed to initialize database. Worker may not function correctly.")
            return 1
        
        # Get broker (needed for health server)
        broker = get_broker()
        
        # Create worker
        worker = create_worker(config)
        if worker is None:
            logger.warning(f"Skipping {config.worker_type} worker startup")
            return 0
        
        # Start health check server
        health_port = get_worker_port(config.worker_type)
        health_server = WorkerHealthServer(
            worker=worker,
            broker=broker,
            port=health_port,
            worker_type=config.worker_type,
        )
        health_server.start()
        logger.info(f"Health check server started on port {health_port}")
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            health_server.stop()
            worker.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run worker (blocks until shutdown)
        logger.info(f"Starting {config.worker_type} worker...")
        worker.run()
        
        return 0
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())


