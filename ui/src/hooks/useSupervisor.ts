/**
 * TanStack Query hooks for supervisor dashboard endpoints
 * 
 * Provides hooks for:
 * - Supervisor overview
 * - Escalations list
 * - Policy violations list
 * 
 * All hooks include tenantId in query keys and handle errors via snackbar.
 */

import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { useTenant } from './useTenant'
import {
  getSupervisorOverview,
  getSupervisorEscalations,
  getSupervisorPolicyViolations,
  type SupervisorOverviewParams,
  type EscalationsParams,
  type PolicyViolationsParams,
} from '../api/supervisor'
import type {
  SupervisorOverview,
  EscalationsResponse,
  PolicyViolationsResponse,
} from '../types'

/**
 * Query key factory for supervisor-related queries
 */
export const supervisorKeys = {
  /** All supervisor queries */
  all: ['supervisor'] as const,
  /** Supervisor overview query */
  overview: (tenantId: string | null, params?: SupervisorOverviewParams) =>
    [...supervisorKeys.all, 'overview', tenantId, params] as const,
  /** Escalations queries */
  escalations: (tenantId: string | null, params?: EscalationsParams) =>
    [...supervisorKeys.all, 'escalations', tenantId, params] as const,
  /** Policy violations queries */
  policyViolations: (tenantId: string | null, params?: PolicyViolationsParams) =>
    [...supervisorKeys.all, 'policy-violations', tenantId, params] as const,
}

/**
 * Hook to fetch supervisor overview dashboard data
 * 
 * @param params Optional query parameters (domain, from_ts, to_ts)
 * @returns Query result with supervisor overview
 */
export function useSupervisorOverview(
  params?: SupervisorOverviewParams
): UseQueryResult<SupervisorOverview, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: supervisorKeys.overview(tenantId, params),
    queryFn: () => getSupervisorOverview(params),
    enabled: !!tenantId,
    staleTime: 60_000, // 1 minute (dashboard data updates less frequently)
  })
}

/**
 * Hook to fetch list of escalated exceptions
 * 
 * @param params Optional query parameters (domain, limit)
 * @returns Query result with escalations list
 */
export function useSupervisorEscalations(
  params?: EscalationsParams
): UseQueryResult<EscalationsResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: supervisorKeys.escalations(tenantId, params),
    queryFn: () => getSupervisorEscalations(params),
    enabled: !!tenantId,
    staleTime: 30_000, // 30 seconds (escalations may update)
  })
}

/**
 * Hook to fetch recent policy violation events
 * 
 * @param params Optional query parameters (domain, limit)
 * @returns Query result with policy violations list
 */
export function useSupervisorPolicyViolations(
  params?: PolicyViolationsParams
): UseQueryResult<PolicyViolationsResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: supervisorKeys.policyViolations(tenantId, params),
    queryFn: () => getSupervisorPolicyViolations(params),
    enabled: !!tenantId,
    staleTime: 30_000, // 30 seconds (violations may update)
  })
}

