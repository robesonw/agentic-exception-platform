/**
 * Supervisor dashboard types
 * 
 * Mirrors backend models from:
 * - src/api/routes/router_supervisor_dashboard.py (OverviewResponse, EscalationItem, PolicyViolationItem)
 * - docs/03-data-models-apis.md
 */

/**
 * Counts by severity and status
 * Mirrors counts field in OverviewResponse from router_supervisor_dashboard.py
 */
export interface SeverityStatusCounts {
  /** Counts keyed by severity level */
  [severity: string]: {
    /** Counts keyed by status */
    [status: string]: number
  }
}

/**
 * Optimization suggestions summary
 * Mirrors optimization_suggestions_summary field in OverviewResponse
 */
export interface OptimizationSuggestionsSummary {
  /** Summary data */
  [key: string]: unknown
}

/**
 * Supervisor overview response
 * Mirrors OverviewResponse from router_supervisor_dashboard.py
 */
export interface SupervisorOverview {
  /** Counts by severity and status */
  counts: SeverityStatusCounts
  /** Number of escalated exceptions */
  escalations_count: number
  /** Number of pending approvals */
  pending_approvals_count: number
  /** Top policy violations */
  top_policy_violations: PolicyViolationItem[]
  /** Summary of optimization suggestions */
  optimization_suggestions_summary: OptimizationSuggestionsSummary
}

/**
 * Escalation item
 * Mirrors EscalationItem from router_supervisor_dashboard.py
 */
export interface EscalationItem extends Record<string, unknown> {
  /** Exception identifier */
  exception_id: string
  /** Tenant identifier */
  tenant_id: string
  /** Domain name (optional) */
  domain?: string | null
  /** Exception type (optional) */
  exception_type?: string | null
  /** Severity level (optional) */
  severity?: string | null
  /** Timestamp (optional) */
  timestamp?: string | null
  /** Reason for escalation */
  escalation_reason: string
}

/**
 * Escalations response
 * Mirrors EscalationsResponse from router_supervisor_dashboard.py
 */
export interface EscalationsResponse {
  /** List of escalated exceptions */
  escalations: EscalationItem[]
  /** Total number of escalations */
  total: number
}

/**
 * Policy violation item
 * Mirrors PolicyViolationItem from router_supervisor_dashboard.py
 */
export interface PolicyViolationItem extends Record<string, unknown> {
  /** Exception identifier */
  exception_id: string
  /** Tenant identifier */
  tenant_id: string
  /** Domain name (optional) */
  domain?: string | null
  /** Timestamp */
  timestamp: string
  /** Type of violation */
  violation_type: string
  /** Rule that was violated */
  violated_rule: string
  /** Decision that violated the rule */
  decision: string
}

/**
 * Policy violations response
 * Mirrors PolicyViolationsResponse from router_supervisor_dashboard.py
 */
export interface PolicyViolationsResponse {
  /** List of policy violations */
  violations: PolicyViolationItem[]
  /** Total number of violations */
  total: number
}

