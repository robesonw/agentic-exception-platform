#!/usr/bin/env python3
"""
Replay Dead Letter Queue events.

This script:
- Re-publishes DLQ events back to their original topic
- Uses a new event_id but preserves the same correlation_id
- Writes an audit entry "DLQReplayed"
- Does NOT delete DLQ entries

Usage:
    # Replay a specific DLQ entry by ID
    python scripts/replay_dlq.py --dlq_id <event_id> --tenant <tenant_id>

    # Replay all DLQ entries for a tenant since a timestamp
    python scripts/replay_dlq.py --tenant <tenant_id> --since "2024-01-01T00:00:00Z"

Examples:
    # Replay a specific DLQ entry
    python scripts/replay_dlq.py --dlq_id evt_abc123 --tenant TENANT_FINANCE_001

    # Replay all DLQ entries for tenant since yesterday
    python scripts/replay_dlq.py --tenant TENANT_FINANCE_001 --since "2024-01-15T00:00:00Z"

Prerequisites:
    1. PostgreSQL must be running
    2. Kafka must be running
    3. Event store must be accessible
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.audit.logger import AuditLogger
from src.infrastructure.db.session import get_db_session_context, initialize_database
from src.infrastructure.repositories.dead_letter_repository import DeadLetterEventRepository
from src.messaging.broker import get_broker
from src.messaging.event_publisher import EventPublisherService
from src.messaging.event_store import DatabaseEventStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DLQReplayer:
    """Replays Dead Letter Queue events back to their original topics."""

    def __init__(self):
        """Initialize replayer with broker and event publisher."""
        broker = get_broker()
        event_store = DatabaseEventStore()
        self.event_publisher = EventPublisherService(broker=broker, event_store=event_store)
        
        # Create audit logger for recording replay operations
        run_id = f"dlq_replay_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.audit_logger = AuditLogger(run_id=run_id)

    async def replay_dlq_entry(self, dlq_entry) -> bool:
        """
        Replay a single DLQ entry.
        
        Args:
            dlq_entry: DeadLetterEvent instance
            
        Returns:
            True if replay succeeded, False otherwise
        """
        try:
            # Extract correlation_id from event_metadata if available
            correlation_id = None
            if dlq_entry.event_metadata:
                correlation_id = dlq_entry.event_metadata.get("correlation_id")
            
            # If correlation_id not in metadata, try to use exception_id as fallback
            if not correlation_id and dlq_entry.exception_id:
                correlation_id = dlq_entry.exception_id
            
            # Generate new event_id (preserve correlation_id for traceability)
            new_event_id = str(uuid4())
            
            # Build event dictionary from DLQ entry
            # The DLQ entry stores payload and metadata separately, so we reconstruct the full event
            event_dict = {
                "event_id": new_event_id,
                "event_type": dlq_entry.event_type,
                "tenant_id": dlq_entry.tenant_id,
                "exception_id": dlq_entry.exception_id,
                "correlation_id": correlation_id,
                "payload": dlq_entry.payload or {},
                "metadata": dlq_entry.event_metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": 1,
            }
            
            logger.info(
                f"Replaying DLQ entry: event_id={dlq_entry.event_id} -> new_event_id={new_event_id}, "
                f"topic={dlq_entry.original_topic}, correlation_id={correlation_id}"
            )
            
            # Publish event to original topic
            await self.event_publisher.publish_event(
                topic=dlq_entry.original_topic,
                event=event_dict,
            )
            
            # Write audit entry "DLQReplayed"
            self.audit_logger._write_log_entry(
                event_type="DLQReplayed",
                data={
                    "original_event_id": dlq_entry.event_id,
                    "new_event_id": new_event_id,
                    "event_type": dlq_entry.event_type,
                    "tenant_id": dlq_entry.tenant_id,
                    "exception_id": dlq_entry.exception_id,
                    "correlation_id": correlation_id,
                    "original_topic": dlq_entry.original_topic,
                    "failure_reason": dlq_entry.failure_reason,
                    "retry_count": dlq_entry.retry_count,
                    "worker_type": dlq_entry.worker_type,
                    "replayed_at": datetime.now(timezone.utc).isoformat(),
                },
                tenant_id=dlq_entry.tenant_id,
            )
            
            logger.info(
                f"Successfully replayed DLQ entry: event_id={dlq_entry.event_id} -> new_event_id={new_event_id}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to replay DLQ entry {dlq_entry.event_id}: {e}",
                exc_info=True,
            )
            return False

    async def replay_by_id(self, dlq_id: str, tenant_id: str) -> int:
        """
        Replay a specific DLQ entry by event_id.
        
        Args:
            dlq_id: Original event_id of the DLQ entry
            tenant_id: Tenant identifier
            
        Returns:
            Number of entries successfully replayed (0 or 1)
        """
        async with get_db_session_context() as session:
            dlq_repo = DeadLetterEventRepository(session)
            dlq_entry = await dlq_repo.get_dlq_entry(event_id=dlq_id, tenant_id=tenant_id)
            
            if not dlq_entry:
                logger.warning(f"DLQ entry not found: event_id={dlq_id}, tenant_id={tenant_id}")
                return 0
            
            success = await self.replay_dlq_entry(dlq_entry)
            return 1 if success else 0

    async def replay_by_tenant_since(
        self, tenant_id: str, since: datetime
    ) -> tuple[int, int]:
        """
        Replay all DLQ entries for a tenant since a timestamp.
        
        Args:
            tenant_id: Tenant identifier
            since: Timestamp to filter entries (entries with failed_at >= since)
            
        Returns:
            Tuple of (successful_count, total_count)
        """
        async with get_db_session_context() as session:
            dlq_repo = DeadLetterEventRepository(session)
            
            # List all DLQ entries for tenant (ordered by failed_at desc)
            result = await dlq_repo.list_dlq_entries(
                tenant_id=tenant_id,
                limit=10000,  # Large limit to get all entries
                offset=0,
                order_by="failed_at",
                order_desc=True,
            )
            
            # Filter entries where failed_at >= since
            entries_to_replay = [
                entry for entry in result.items
                if entry.failed_at and entry.failed_at >= since
            ]
            
            if not entries_to_replay:
                logger.info(
                    f"No DLQ entries found for tenant {tenant_id} since {since.isoformat()}"
                )
                return 0, 0
            
            logger.info(
                f"Found {len(entries_to_replay)} DLQ entries to replay for tenant {tenant_id}"
            )
            
            # Replay each entry
            successful = 0
            for entry in entries_to_replay:
                if await self.replay_dlq_entry(entry):
                    successful += 1
            
            return successful, len(entries_to_replay)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Replay Dead Letter Queue events back to their original topics"
    )
    
    # Input options: either --dlq_id or --tenant --since
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--dlq_id",
        type=str,
        help="Original event_id of the DLQ entry to replay",
    )
    input_group.add_argument(
        "--tenant",
        type=str,
        help="Tenant identifier (required with --since)",
    )
    
    parser.add_argument(
        "--since",
        type=str,
        help="ISO timestamp to filter entries (required with --tenant). "
             "Format: '2024-01-01T00:00:00Z' or '2024-01-01T00:00:00+00:00'",
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.dlq_id:
        if not args.tenant:
            parser.error("--tenant is required when using --dlq_id")
        tenant_id = args.tenant
    elif args.tenant:
        if not args.since:
            parser.error("--since is required when using --tenant")
        tenant_id = args.tenant
        try:
            # Parse ISO timestamp
            since_str = args.since
            if since_str.endswith("Z"):
                since_str = since_str[:-1] + "+00:00"
            since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
        except ValueError as e:
            parser.error(f"Invalid --since timestamp format: {e}. Use ISO format: '2024-01-01T00:00:00Z'")
    else:
        parser.error("Either --dlq_id or --tenant --since must be provided")
    
    # Initialize database
    logger.info("Initializing database connection...")
    db_initialized = await initialize_database()
    if not db_initialized:
        logger.error("Failed to initialize database. Exiting.")
        sys.exit(1)
    
    # Create replayer
    replayer = DLQReplayer()
    
    # Execute replay
    try:
        if args.dlq_id:
            logger.info(f"Replaying DLQ entry: event_id={args.dlq_id}, tenant_id={tenant_id}")
            count = await replayer.replay_by_id(dlq_id=args.dlq_id, tenant_id=tenant_id)
            if count == 0:
                logger.warning("No DLQ entry found or replay failed")
                sys.exit(1)
            else:
                logger.info(f"Successfully replayed 1 DLQ entry")
        else:
            logger.info(f"Replaying DLQ entries for tenant {tenant_id} since {since.isoformat()}")
            successful, total = await replayer.replay_by_tenant_since(
                tenant_id=tenant_id, since=since
            )
            logger.info(
                f"Replay complete: {successful}/{total} entries successfully replayed"
            )
            if successful == 0:
                sys.exit(1)
    except Exception as e:
        logger.error(f"Replay failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

