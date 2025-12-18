#!/usr/bin/env python3
"""
Generate audit report for an exception.

Fetches all events for a given exception_id, orders them chronologically,
and generates a markdown report with timestamps, decisions, playbook steps,
and tool executions.

Usage:
    python scripts/generate_audit_report.py --exception_id <id> --tenant_id <tenant_id>

Example:
    python scripts/generate_audit_report.py --exception_id exc_001 --tenant_id tenant_001

Output:
    Saves report to output/exception_audit_<id>.md
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.session import get_db_session_context, initialize_database
from src.infrastructure.repositories.event_store_repository import (
    EventFilter,
    EventStoreRepository,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AuditReportGenerator:
    """Generates markdown audit reports for exceptions."""
    
    def __init__(self):
        """Initialize report generator."""
        self.output_dir = project_root / "output"
        self.output_dir.mkdir(exist_ok=True)
    
    def format_timestamp(self, timestamp: datetime) -> str:
        """Format timestamp for display."""
        if timestamp:
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    return timestamp
            return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        return "N/A"
    
    def format_payload(self, payload: dict[str, Any], max_length: int = 200) -> str:
        """Format payload as JSON string, truncating if too long."""
        json_str = json.dumps(payload, indent=2, default=str)
        if len(json_str) > max_length:
            return json_str[:max_length] + "\n... (truncated)"
        return json_str
    
    def format_event_section(self, event: dict[str, Any]) -> str:
        """Format a single event as a markdown section."""
        event_type = event.get("event_type", "Unknown")
        timestamp = event.get("timestamp")
        payload = event.get("payload", {})
        metadata = event.get("metadata", {})
        
        lines = []
        lines.append(f"### {event_type}")
        lines.append(f"**Timestamp:** {self.format_timestamp(timestamp)}")
        lines.append(f"**Event ID:** `{event.get('event_id', 'N/A')}`")
        
        # Format event-specific information
        if event_type == "ExceptionIngested":
            lines.append(f"**Source System:** {payload.get('source_system', 'N/A')}")
            raw_payload = payload.get("raw_payload", {})
            if raw_payload:
                lines.append(f"**Raw Payload:**")
                lines.append(f"```json\n{self.format_payload(raw_payload)}\n```")
        
        elif event_type == "ExceptionNormalized":
            exception_type = payload.get("exception_type") or payload.get("normalized_exception", {}).get("exceptionType")
            if exception_type:
                lines.append(f"**Exception Type:** {exception_type}")
            normalized = payload.get("normalized_exception", {})
            if normalized:
                lines.append(f"**Normalized Exception:**")
                lines.append(f"```json\n{self.format_payload(normalized)}\n```")
        
        elif event_type == "TriageCompleted":
            classification = payload.get("classification") or payload.get("exception_type")
            severity = payload.get("severity")
            confidence = payload.get("confidence")
            if classification:
                lines.append(f"**Classification:** {classification}")
            if severity:
                lines.append(f"**Severity:** {severity}")
            if confidence is not None:
                lines.append(f"**Confidence:** {confidence:.2f}" if isinstance(confidence, (int, float)) else f"**Confidence:** {confidence}")
            evidence = payload.get("evidence", [])
            if evidence:
                lines.append(f"**Evidence:**")
                for item in evidence[:5]:  # Limit to first 5
                    lines.append(f"  - {item}")
                if len(evidence) > 5:
                    lines.append(f"  - ... ({len(evidence) - 5} more)")
        
        elif event_type == "PolicyEvaluationCompleted":
            decision = payload.get("decision") or payload.get("actionability")
            guardrails_checked = payload.get("guardrails_checked", [])
            if decision:
                lines.append(f"**Decision:** {decision}")
            if guardrails_checked:
                lines.append(f"**Guardrails Checked:** {len(guardrails_checked)}")
                for guardrail in guardrails_checked[:3]:
                    guardrail_id = guardrail.get("guardrail_id") or guardrail.get("id", "Unknown")
                    status = guardrail.get("status") or guardrail.get("violated", False)
                    lines.append(f"  - {guardrail_id}: {'Violated' if status else 'Passed'}")
                if len(guardrails_checked) > 3:
                    lines.append(f"  - ... ({len(guardrails_checked) - 3} more)")
        
        elif event_type == "PlaybookMatched":
            playbook_id = payload.get("playbook_id")
            playbook_name = payload.get("playbook_name") or payload.get("name")
            confidence = payload.get("confidence")
            if playbook_name:
                lines.append(f"**Playbook:** {playbook_name}")
            if playbook_id:
                lines.append(f"**Playbook ID:** {playbook_id}")
            if confidence is not None:
                lines.append(f"**Confidence:** {confidence:.2f}" if isinstance(confidence, (int, float)) else f"**Confidence:** {confidence}")
            steps = payload.get("steps", [])
            if steps:
                lines.append(f"**Steps:** {len(steps)}")
        
        elif event_type == "StepExecutionRequested":
            step_order = payload.get("step_order")
            step_name = payload.get("step_name") or payload.get("name")
            step_action = payload.get("step_action", {})
            action_type = step_action.get("action_type") or step_action.get("type")
            if step_order is not None:
                lines.append(f"**Step Order:** {step_order}")
            if step_name:
                lines.append(f"**Step Name:** {step_name}")
            if action_type:
                lines.append(f"**Action Type:** {action_type}")
        
        elif event_type == "ToolExecutionRequested":
            tool_id = payload.get("tool_id")
            tool_name = payload.get("tool_name") or payload.get("name")
            execution_id = payload.get("execution_id")
            if tool_name:
                lines.append(f"**Tool:** {tool_name}")
            if tool_id:
                lines.append(f"**Tool ID:** {tool_id}")
            if execution_id:
                lines.append(f"**Execution ID:** `{execution_id}`")
            input_payload = payload.get("input_payload") or payload.get("tool_params", {})
            if input_payload:
                lines.append(f"**Input:**")
                lines.append(f"```json\n{self.format_payload(input_payload)}\n```")
        
        elif event_type == "ToolExecutionCompleted":
            tool_id = payload.get("tool_id")
            tool_name = payload.get("tool_name")
            execution_id = payload.get("execution_id")
            status = payload.get("status")
            result = payload.get("output_payload") or payload.get("result", {})
            error_message = payload.get("error_message")
            if tool_name:
                lines.append(f"**Tool:** {tool_name}")
            if tool_id:
                lines.append(f"**Tool ID:** {tool_id}")
            if execution_id:
                lines.append(f"**Execution ID:** `{execution_id}`")
            if status:
                status_emoji = "✅" if status == "success" else "❌" if status == "failure" else "⏳"
                lines.append(f"**Status:** {status_emoji} {status.upper()}")
            if error_message:
                lines.append(f"**Error:** {error_message}")
            if result and status == "success":
                lines.append(f"**Result:**")
                lines.append(f"```json\n{self.format_payload(result)}\n```")
        
        elif event_type == "PlaybookStepCompletionRequested":
            step_order = payload.get("step_order")
            step_name = payload.get("step_name")
            if step_order is not None:
                lines.append(f"**Step Order:** {step_order}")
            if step_name:
                lines.append(f"**Step Name:** {step_name}")
        
        # Add correlation ID if available
        correlation_id = event.get("correlation_id")
        if correlation_id:
            lines.append(f"**Correlation ID:** `{correlation_id}`")
        
        # Add full payload if verbose or if no specific formatting applied
        if not any(line.startswith("**") for line in lines[3:]):  # No specific fields added
            lines.append(f"**Payload:**")
            lines.append(f"```json\n{self.format_payload(payload)}\n```")
        
        lines.append("")  # Empty line between events
        return "\n".join(lines)
    
    async def generate_report(
        self, exception_id: str, tenant_id: str
    ) -> str:
        """
        Generate audit report for an exception.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            
        Returns:
            Markdown report content
        """
        async with get_db_session_context() as session:
            event_repo = EventStoreRepository(session)
            
            # Fetch all events (paginate if needed)
            all_events = []
            page = 1
            page_size = 100
            
            while True:
                result = await event_repo.get_events_by_exception(
                    exception_id=exception_id,
                    tenant_id=tenant_id,
                    filters=None,
                    page=page,
                    page_size=page_size,
                )
                
                # Convert EventLog to dict
                for event_log in result.items:
                    event_dict = {
                        "event_id": event_log.event_id,
                        "event_type": event_log.event_type,
                        "tenant_id": event_log.tenant_id,
                        "exception_id": event_log.exception_id,
                        "correlation_id": event_log.correlation_id,
                        "timestamp": event_log.timestamp,
                        "payload": event_log.payload or {},
                        "metadata": event_log.metadata or {},
                        "version": event_log.version,
                    }
                    all_events.append(event_dict)
                
                if len(all_events) >= result.total:
                    break
                
                page += 1
            
            # Sort by timestamp ascending (chronological order - oldest first)
            # Repository returns newest first, so we reverse to get chronological order
            all_events.sort(key=lambda e: e.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc))
            
            # Generate markdown report
            lines = []
            lines.append(f"# Exception Audit Report")
            lines.append("")
            lines.append(f"**Exception ID:** `{exception_id}`")
            lines.append(f"**Tenant ID:** `{tenant_id}`")
            lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            lines.append(f"**Total Events:** {len(all_events)}")
            lines.append("")
            lines.append("---")
            lines.append("")
            
            # Summary section
            lines.append("## Summary")
            lines.append("")
            
            # Count event types
            event_type_counts = {}
            for event in all_events:
                event_type = event.get("event_type", "Unknown")
                event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
            
            lines.append("### Event Types")
            for event_type, count in sorted(event_type_counts.items()):
                lines.append(f"- **{event_type}:** {count}")
            lines.append("")
            
            # Timeline section
            lines.append("## Timeline")
            lines.append("")
            
            if not all_events:
                lines.append("*No events found for this exception.*")
            else:
                for idx, event in enumerate(all_events, 1):
                    lines.append(f"### Event {idx}")
                    lines.append(self.format_event_section(event))
            
            return "\n".join(lines)
    
    async def save_report(self, exception_id: str, tenant_id: str) -> tuple[Path, int]:
        """
        Generate and save audit report.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            
        Returns:
            Tuple of (path to saved report file, total event count)
        """
        logger.info(f"Generating audit report for exception {exception_id} (tenant: {tenant_id})")
        
        report_content = await self.generate_report(exception_id, tenant_id)
        
        # Count events from report content (simple count of "### Event" lines)
        event_count = report_content.count("### Event ")
        
        # Save to file
        output_file = self.output_dir / f"exception_audit_{exception_id}.md"
        output_file.write_text(report_content, encoding="utf-8")
        
        logger.info(f"Audit report saved to: {output_file}")
        return output_file, event_count


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate audit report for an exception"
    )
    
    parser.add_argument(
        "--exception_id",
        type=str,
        required=True,
        help="Exception identifier",
    )
    
    parser.add_argument(
        "--tenant_id",
        type=str,
        required=True,
        help="Tenant identifier",
    )
    
    args = parser.parse_args()
    
    # Initialize database
    logger.info("Initializing database connection...")
    db_initialized = await initialize_database()
    if not db_initialized:
        logger.error("Failed to initialize database. Exiting.")
        sys.exit(1)
    
    # Generate report
    generator = AuditReportGenerator()
    try:
        output_file, event_count = await generator.save_report(
            exception_id=args.exception_id,
            tenant_id=args.tenant_id,
        )
        print(f"\n✅ Audit report generated successfully!")
        print(f"📄 Report saved to: {output_file}")
        print(f"📊 Total events: {event_count}")
    except Exception as e:
        logger.error(f"Failed to generate audit report: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

