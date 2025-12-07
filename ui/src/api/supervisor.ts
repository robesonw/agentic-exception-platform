/**
 * API client for supervisor dashboard endpoints
 * 
 * Mirrors backend routes from:
 * - src/api/routes/router_supervisor_dashboard.py
 * 
 * All functions automatically include tenantId via httpClient interceptors.
 */

import { httpClient } from '../utils/httpClient'
import type {
  SupervisorOverview,
  EscalationsResponse,
  PolicyViolationsResponse,
} from '../types'

/**
 * Parameters for supervisor overview
 * Mirrors query parameters from GET /ui/supervisor/overview
 */
export interface SupervisorOverviewParams {
  /** Optional domain filter */
  domain?: string
  /** Start timestamp (ISO format, optional) */
  from_ts?: string
  /** End timestamp (ISO format, optional) */
  to_ts?: string
}

/**
 * Parameters for escalations list
 * Mirrors query parameters from GET /ui/supervisor/escalations
 */
export interface EscalationsParams {
  /** Optional domain filter */
  domain?: string
  /** Maximum number of escalations to return (default: 50, max: 500) */
  limit?: number
}

/**
 * Parameters for policy violations list
 * Mirrors query parameters from GET /ui/supervisor/policy-violations
 */
export interface PolicyViolationsParams {
  /** Optional domain filter */
  domain?: string
  /** Maximum number of violations to return (default: 50, max: 500) */
  limit?: number
}

/**
 * Get supervisor overview dashboard data
 * GET /ui/supervisor/overview
 * 
 * @param params Optional query parameters
 * @returns Supervisor overview with counts, escalations, violations, and suggestions
 */
export async function getSupervisorOverview(
  params?: SupervisorOverviewParams
): Promise<SupervisorOverview> {
  return httpClient.get<SupervisorOverview>('/ui/supervisor/overview', {
    params,
  })
}

/**
 * Get list of escalated exceptions
 * GET /ui/supervisor/escalations
 * 
 * @param params Optional query parameters
 * @returns List of escalated exceptions
 */
export async function getSupervisorEscalations(
  params?: EscalationsParams
): Promise<EscalationsResponse> {
  return httpClient.get<EscalationsResponse>('/ui/supervisor/escalations', {
    params,
  })
}

/**
 * Get recent policy violation events
 * GET /ui/supervisor/policy-violations
 * 
 * @param params Optional query parameters
 * @returns List of policy violations
 */
export async function getSupervisorPolicyViolations(
  params?: PolicyViolationsParams
): Promise<PolicyViolationsResponse> {
  return httpClient.get<PolicyViolationsResponse>('/ui/supervisor/policy-violations', {
    params,
  })
}

