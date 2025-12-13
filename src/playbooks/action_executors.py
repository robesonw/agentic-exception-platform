"""
Playbook Step Action Executors for Phase 7 MVP.

Executes safe, low-risk actions for playbook steps.
Reference: docs/phase7-playbooks-mvp.md Sections 3.2 & 4.3
"""

import json
import logging
import re
from typing import Any, Optional
from uuid import uuid4

from src.infrastructure.db.models import ActorType, Exception as ExceptionModel, ExceptionStatus
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord
from src.models.tenant_policy import TenantPolicyPack
from src.notify.service import NotificationService
from src.repository.dto import ExceptionEventCreateDTO, ExceptionUpdateDTO
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository

logger = logging.getLogger(__name__)


class ActionExecutorError(Exception):
    """Raised when action execution fails."""
    pass


def resolve_placeholders(
    template: dict[str, Any] | str,
    exception: ExceptionRecord | ExceptionModel,
    domain_pack: Optional[DomainPack] = None,
    policy_pack: Optional[TenantPolicyPack] = None,
) -> dict[str, Any] | str:
    """
    Resolve placeholders in a template using exception, domain pack, and policy pack data.
    
    Supports placeholders in format:
    - {exception.exception_id}
    - {exception.entity}
    - {exception.amount}
    - {exception.severity}
    - {exception.normalized_context.key}
    - {domain_pack.domain_name}
    - {policy_pack.tenant_id}
    - {policy_pack.domain_name}
    
    For nested dict access, use dot notation: {exception.normalized_context.domain}
    
    Args:
        template: Template dict or string with placeholders
        exception: ExceptionRecord or Exception instance
        domain_pack: Optional DomainPack instance
        policy_pack: Optional TenantPolicyPack instance
        
    Returns:
        Resolved template (same type as input)
    """
    # Convert exception to dict-like structure for easy access
    exception_dict: dict[str, Any] = {}
    
    # Handle both ExceptionRecord and Exception models
    if isinstance(exception, ExceptionRecord):
        exception_dict = {
            "exception_id": exception.exception_id,
            "tenant_id": exception.tenant_id,
            "source_system": exception.source_system,
            "exception_type": exception.exception_type,
            "severity": exception.severity.value if exception.severity else None,
            "timestamp": exception.timestamp.isoformat() if hasattr(exception.timestamp, "isoformat") else str(exception.timestamp),
            "normalized_context": exception.normalized_context or {},
            "resolution_status": exception.resolution_status.value if exception.resolution_status else None,
        }
    elif isinstance(exception, Exception):
        exception_dict = {
            "exception_id": exception.exception_id,
            "tenant_id": exception.tenant_id,
            "source_system": exception.source_system,
            "exception_type": exception.type,
            "severity": exception.severity.value if exception.severity else None,
            "timestamp": exception.timestamp.isoformat() if hasattr(exception.timestamp, "isoformat") else str(exception.timestamp),
            "normalized_context": {},  # Exception model doesn't have normalized_context directly
            "resolution_status": exception.status.value if exception.status else None,
            "entity": exception.entity,
            "amount": exception.amount,
            "owner": exception.owner,
        }
    
    # Build context for placeholder resolution
    context: dict[str, Any] = {
        "exception": exception_dict,
    }
    
    if domain_pack:
        context["domain_pack"] = {
            "domain_name": domain_pack.domain_name,
            "entities": {k: v.model_dump() if hasattr(v, "model_dump") else v for k, v in domain_pack.entities.items()},
        }
    
    if policy_pack:
        context["policy_pack"] = {
            "tenant_id": policy_pack.tenant_id,
            "domain_name": policy_pack.domain_name,
        }
    
    def _resolve_value(value: Any) -> Any:
        """Recursively resolve placeholders in a value."""
        if isinstance(value, str):
            # Replace placeholders like {exception.exception_id} or {exception.normalized_context.domain}
            def replace_placeholder(match: re.Match) -> str:
                placeholder = match.group(1)
                try:
                    # Split by dots to navigate nested structure
                    parts = placeholder.split(".")
                    result = context
                    for part in parts:
                        if isinstance(result, dict):
                            result = result.get(part)
                        elif hasattr(result, part):
                            result = getattr(result, part)
                        else:
                            return match.group(0)  # Return original if not found
                    
                    # Convert result to string if needed
                    if result is None:
                        return ""
                    if isinstance(result, (dict, list)):
                        return json.dumps(result)
                    return str(result)
                except (AttributeError, KeyError, TypeError):
                    logger.warning(f"Could not resolve placeholder: {placeholder}")
                    return match.group(0)  # Return original if resolution fails
            
            return re.sub(r"\{([^}]+)\}", replace_placeholder, value)
        elif isinstance(value, dict):
            return {k: _resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_resolve_value(item) for item in value]
        else:
            return value
    
    if isinstance(template, str):
        return _resolve_value(template)
    else:
        return _resolve_value(template)


async def exec_notify(
    step: Any,  # PlaybookStep
    exception: ExceptionRecord | ExceptionModel,
    resolved_params: dict[str, Any],
    tenant_id: str,
    notification_service: Optional[NotificationService] = None,
    policy_pack: Optional[TenantPolicyPack] = None,
) -> dict[str, Any]:
    """
    Execute notify action.
    
    For MVP, logs the notification or sends via NotificationService if available.
    
    Args:
        step: PlaybookStep instance
        exception: ExceptionRecord or Exception instance
        resolved_params: Resolved step parameters (should contain channel, subject, message, etc.)
        tenant_id: Tenant identifier
        notification_service: Optional NotificationService instance
        policy_pack: Optional TenantPolicyPack for notification policies
        
    Returns:
        Result dict with success status and details
    """
    channel = resolved_params.get("channel", "log")
    subject = resolved_params.get("subject", f"Notification for exception {exception.exception_id if hasattr(exception, 'exception_id') else 'unknown'}")
    message = resolved_params.get("message", "No message provided")
    template_id = resolved_params.get("template_id")
    group = resolved_params.get("group", "DefaultOps")
    
    result: dict[str, Any] = {
        "action": "notify",
        "success": True,
        "channel": channel,
        "subject": subject,
        "message": message,
    }
    
    if notification_service and channel != "log":
        try:
            notification_policies = None
            if policy_pack and hasattr(policy_pack, "notification_policies"):
                notification_policies = policy_pack.notification_policies.model_dump() if hasattr(policy_pack.notification_policies, "model_dump") else policy_pack.notification_policies
            
            send_result = notification_service.send_notification(
                tenant_id=tenant_id,
                group=group,
                subject=subject,
                message=message,
                notification_policies=notification_policies,
            )
            result["notification_result"] = send_result
            logger.info(
                f"Sent notification via {channel} for exception {exception.exception_id if hasattr(exception, 'exception_id') else 'unknown'}"
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}", exc_info=True)
            result["success"] = False
            result["error"] = str(e)
    else:
        # Log-only mode (MVP default)
        logger.info(
            f"[NOTIFY] Channel: {channel}, Group: {group}, Subject: {subject}, "
            f"Message: {message}, Template: {template_id}"
        )
        result["logged"] = True
    
    return result


async def exec_assign_owner(
    step: Any,  # PlaybookStep
    exception: ExceptionRecord | ExceptionModel,
    resolved_params: dict[str, Any],
    tenant_id: str,
    exception_repository: ExceptionRepository,
) -> dict[str, Any]:
    """
    Execute assign_owner action.
    
    Updates exception.owner field.
    
    Args:
        step: PlaybookStep instance
        exception: ExceptionRecord or Exception instance
        resolved_params: Resolved step parameters (should contain queue or user_id)
        tenant_id: Tenant identifier
        exception_repository: ExceptionRepository instance
        
    Returns:
        Result dict with success status and new owner
    """
    exception_id = exception.exception_id if hasattr(exception, "exception_id") else None
    if not exception_id:
        raise ActionExecutorError("Exception does not have exception_id")
    
    # Resolve owner from queue or user_id
    owner = resolved_params.get("user_id") or resolved_params.get("queue")
    if not owner:
        raise ActionExecutorError("assign_owner requires 'user_id' or 'queue' parameter")
    
    # Update exception
    await exception_repository.update_exception(
        tenant_id=tenant_id,
        exception_id=exception_id,
        updates=ExceptionUpdateDTO(owner=owner),
    )
    
    logger.info(f"Assigned owner '{owner}' to exception {exception_id}")
    
    return {
        "action": "assign_owner",
        "success": True,
        "owner": owner,
    }


async def exec_set_status(
    step: Any,  # PlaybookStep
    exception: ExceptionRecord | ExceptionModel,
    resolved_params: dict[str, Any],
    tenant_id: str,
    exception_repository: ExceptionRepository,
) -> dict[str, Any]:
    """
    Execute set_status action.
    
    Updates exception.status field with controlled transitions.
    
    Args:
        step: PlaybookStep instance
        exception: ExceptionRecord or Exception instance
        resolved_params: Resolved step parameters (should contain status)
        tenant_id: Tenant identifier
        exception_repository: ExceptionRepository instance
        
    Returns:
        Result dict with success status and new status
    """
    exception_id = exception.exception_id if hasattr(exception, "exception_id") else None
    if not exception_id:
        raise ActionExecutorError("Exception does not have exception_id")
    
    status_str = resolved_params.get("status")
    if not status_str:
        raise ActionExecutorError("set_status requires 'status' parameter")
    
    # Map status string to ExceptionStatus enum
    status_map = {
        "open": ExceptionStatus.OPEN,
        "analyzing": ExceptionStatus.ANALYZING,
        "resolved": ExceptionStatus.RESOLVED,
        "escalated": ExceptionStatus.ESCALATED,
    }
    
    status_lower = status_str.lower()
    if status_lower not in status_map:
        raise ActionExecutorError(f"Invalid status: {status_str}. Valid values: {list(status_map.keys())}")
    
    new_status = status_map[status_lower]
    
    # TODO: Add controlled transition validation (e.g., cannot jump from open to resolved)
    # For MVP, we allow any transition but log it
    
    # Update exception
    await exception_repository.update_exception(
        tenant_id=tenant_id,
        exception_id=exception_id,
        updates=ExceptionUpdateDTO(status=new_status),
    )
    
    logger.info(f"Set status '{new_status.value}' for exception {exception_id}")
    
    return {
        "action": "set_status",
        "success": True,
        "status": new_status.value,
    }


async def exec_add_comment(
    step: Any,  # PlaybookStep
    exception: ExceptionRecord | ExceptionModel,
    resolved_params: dict[str, Any],
    tenant_id: str,
    event_repository: ExceptionEventRepository,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Execute add_comment action.
    
    Appends a comment as an event to the exception event log.
    
    Args:
        step: PlaybookStep instance
        exception: ExceptionRecord or Exception instance
        resolved_params: Resolved step parameters (should contain text_template or text)
        tenant_id: Tenant identifier
        event_repository: ExceptionEventRepository instance
        actor_type: Actor type (default: "system")
        actor_id: Optional actor identifier
        
    Returns:
        Result dict with success status and comment text
    """
    exception_id = exception.exception_id if hasattr(exception, "exception_id") else None
    if not exception_id:
        raise ActionExecutorError("Exception does not have exception_id")
    
    # Get comment text from text_template or text
    comment_text = resolved_params.get("text") or resolved_params.get("text_template", "")
    if not comment_text:
        raise ActionExecutorError("add_comment requires 'text' or 'text_template' parameter")
    
    # Create comment event
    event_id = uuid4()
    event = ExceptionEventCreateDTO(
        event_id=event_id,
        exception_id=exception_id,
        tenant_id=tenant_id,
        event_type="CommentAdded",
        actor_type=actor_type,
        actor_id=actor_id or "PlaybookExecutor",
        payload={
            "comment": comment_text,
            "step_id": step.step_id if hasattr(step, "step_id") else None,
            "step_name": step.name if hasattr(step, "name") else None,
        },
    )
    
    await event_repository.append_event(tenant_id, event)
    
    logger.info(f"Added comment to exception {exception_id}: {comment_text[:50]}...")
    
    return {
        "action": "add_comment",
        "success": True,
        "comment": comment_text,
    }


async def exec_call_tool(
    step: Any,  # PlaybookStep
    exception: ExceptionRecord | ExceptionModel,
    resolved_params: dict[str, Any],
    tenant_id: str,
) -> dict[str, Any]:
    """
    Execute call_tool action (MVP stub).
    
    For MVP, logs the tool call or performs a safe stub.
    Does not actually call external tools.
    
    Args:
        step: PlaybookStep instance
        exception: ExceptionRecord or Exception instance
        resolved_params: Resolved step parameters (should contain tool_id and payload_template)
        tenant_id: Tenant identifier
        
    Returns:
        Result dict with success status and logged details
    """
    tool_id = resolved_params.get("tool_id")
    payload = resolved_params.get("payload") or resolved_params.get("payload_template", {})
    
    if not tool_id:
        raise ActionExecutorError("call_tool requires 'tool_id' parameter")
    
    exception_id = exception.exception_id if hasattr(exception, "exception_id") else "unknown"
    
    # MVP: Log only (no actual tool execution)
    logger.info(
        f"[CALL_TOOL] Would call tool '{tool_id}' for exception {exception_id} "
        f"with payload: {json.dumps(payload, default=str)}"
    )
    
    return {
        "action": "call_tool",
        "success": True,
        "tool_id": tool_id,
        "payload": payload,
        "stub": True,
        "message": "Tool call logged (MVP stub mode)",
    }

