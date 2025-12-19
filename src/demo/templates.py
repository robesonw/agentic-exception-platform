"""
Templates and constants for demo data generation.

Contains domain-specific templates for Finance and Healthcare tenants.
"""

from typing import Any

# Finance domain templates
FINANCE_EXCEPTION_TYPES = [
    "SETTLEMENT_FAILURE",
    "ALLOCATION_MISMATCH",
    "POSITION_DISCREPANCY",
    "REG_REPORT_REJECTED",
    "SEC_MASTER_MISMATCH",
    "CASH_MOVEMENT_ERROR",
    "TRADE_VALIDATION_FAILURE",
]

FINANCE_SOURCE_SYSTEMS = ["Murex", "Calypso", "Bloomberg", "Refinitiv", "InternalTradingSystem"]

FINANCE_ENTITIES = [
    "CPTY_001",
    "CPTY_002",
    "CPTY_003",
    "ACCT_TRADING_001",
    "ACCT_TRADING_002",
    "ACCT_CUSTODY_001",
]

FINANCE_PLAYBOOK_NAMES = [
    "SettlementFailureResolution",
    "AllocationRepairWorkflow",
    "PositionReconciliation",
    "RegReportRegeneration",
    "SecurityMasterSync",
    "CashMovementCorrection",
]

FINANCE_TOOL_NAMES = [
    "getOrder",
    "getExecutions",
    "getAllocations",
    "getPositions",
    "getCashMovements",
    "getSettlement",
    "repairAllocation",
    "triggerSettlementRetry",
    "recalculatePosition",
    "regenerateRegReport",
]

# Healthcare domain templates
HEALTHCARE_EXCEPTION_TYPES = [
    "CLAIM_MISSING_AUTH",
    "CLAIM_CODE_MISMATCH",
    "PROVIDER_CREDENTIAL_EXPIRED",
    "PATIENT_DEMOGRAPHIC_CONFLICT",
    "PHARMACY_DUPLICATE_THERAPY",
    "ELIGIBILITY_COVERAGE_LAPSE",
]

HEALTHCARE_SOURCE_SYSTEMS = ["ClaimsApp", "EHRSystem", "PharmacySystem", "ProviderPortal", "BillingSystem"]

HEALTHCARE_ENTITIES = [
    "PATIENT_001",
    "PATIENT_002",
    "PATIENT_003",
    "PROVIDER_001",
    "PROVIDER_002",
    "FACILITY_001",
]

HEALTHCARE_PLAYBOOK_NAMES = [
    "ClaimAuthValidation",
    "CodeCorrectionWorkflow",
    "ProviderCredentialRenewal",
    "PatientDemographicReconciliation",
    "PharmacySafetyCheck",
    "EligibilityVerification",
]

HEALTHCARE_TOOL_NAMES = [
    "getAuthorization",
    "getClaim",
    "getPatient",
    "getProviderCredential",
    "getMedicationOrders",
    "attachAuthorizationToClaim",
    "reprocessClaim",
    "updateProviderCredential",
    "flagMedicationOrder",
]

# Global tool templates
GLOBAL_TOOL_NAMES = [
    "notifySlack",
    "sendEmail",
    "createJiraTicket",
    "logAuditEvent",
]

# Event type templates
EVENT_TYPES = [
    "ExceptionIngested",
    "ExceptionCreated",
    "TriageCompleted",
    "PolicyEvaluated",
    "PlaybookStarted",
    "PlaybookStepCompleted",
    "PlaybookStepSkipped",
    "ToolExecutionRequested",
    "ToolExecutionCompleted",
    "ToolExecutionFailed",
    "ResolutionSuggested",
    "PlaybookCompleted",
    "FeedbackCaptured",
    "ExceptionResolved",
]

# Actor templates
AGENT_ACTORS = ["IntakeAgent", "TriageAgent", "PolicyAgent", "ResolutionAgent", "FeedbackAgent", "L1Agent", "L2Agent"]
USER_ACTORS = ["user_ops_001", "user_ops_002", "user_admin_001", "user_reviewer_001"]
SYSTEM_ACTORS = ["System", "Scheduler", "WebhookReceiver"]


def get_finance_playbook_conditions(exception_type: str, severity: str) -> dict[str, Any]:
    """Generate playbook matching conditions for Finance domain."""
    conditions: dict[str, Any] = {
        "match": {
            "domain": "CapitalMarketsTrading",
            "exception_type": exception_type,
            "severity_in": [severity.upper()],
        },
        "priority": 10,
    }
    
    # Add policy tags based on exception type
    if "SETTLEMENT" in exception_type:
        conditions["match"]["policy_tags"] = ["settlement", "ops-critical"]
    elif "ALLOCATION" in exception_type:
        conditions["match"]["policy_tags"] = ["allocation", "trading"]
    elif "POSITION" in exception_type:
        conditions["match"]["policy_tags"] = ["position", "reconciliation"]
    elif "REG_REPORT" in exception_type:
        conditions["match"]["policy_tags"] = ["regulatory", "compliance"]
    else:
        conditions["match"]["policy_tags"] = ["general"]
    
    return conditions


def get_healthcare_playbook_conditions(exception_type: str, severity: str) -> dict[str, Any]:
    """Generate playbook matching conditions for Healthcare domain."""
    conditions: dict[str, Any] = {
        "match": {
            "domain": "HealthcareClaimsAndCareOps",
            "exception_type": exception_type,
            "severity_in": [severity.upper()],
        },
        "priority": 10,
    }
    
    # Add policy tags based on exception type
    if "CLAIM" in exception_type:
        conditions["match"]["policy_tags"] = ["claims", "billing"]
    elif "PROVIDER" in exception_type:
        conditions["match"]["policy_tags"] = ["provider", "credentialing"]
    elif "PATIENT" in exception_type:
        conditions["match"]["policy_tags"] = ["patient-master", "data-quality"]
    elif "PHARMACY" in exception_type:
        conditions["match"]["policy_tags"] = ["pharmacy", "patient-safety"]
    elif "ELIGIBILITY" in exception_type:
        conditions["match"]["policy_tags"] = ["eligibility", "coverage"]
    else:
        conditions["match"]["policy_tags"] = ["general"]
    
    return conditions


def get_playbook_steps(action_types: list[str]) -> list[dict[str, Any]]:
    """Generate playbook steps from action types."""
    steps = []
    step_order = 1
    
    for action_type in action_types:
        if action_type == "notify":
            steps.append({
                "name": f"Notify Team - Step {step_order}",
                "action_type": "notify",
                "params": {
                    "channel": "slack",
                    "message": "Exception requires attention",
                },
            })
        elif action_type == "assign_owner":
            steps.append({
                "name": f"Assign Owner - Step {step_order}",
                "action_type": "assign_owner",
                "params": {
                    "owner": "AI Agent (L1)",
                },
            })
        elif action_type == "set_status":
            steps.append({
                "name": f"Set Status - Step {step_order}",
                "action_type": "set_status",
                "params": {
                    "status": "analyzing",
                },
            })
        elif action_type == "add_comment":
            steps.append({
                "name": f"Add Comment - Step {step_order}",
                "action_type": "add_comment",
                "params": {
                    "comment": "Processing exception",
                },
            })
        elif action_type == "call_tool":
            steps.append({
                "name": f"Call Tool - Step {step_order}",
                "action_type": "call_tool",
                "params": {
                    "tool_name": "getOrder",
                    "tool_params": {},
                },
            })
        elif action_type == "escalate":
            steps.append({
                "name": f"Escalate - Step {step_order}",
                "action_type": "escalate",
                "params": {
                    "queue": "EscalationQueue",
                },
            })
        
        step_order += 1
    
    return steps







