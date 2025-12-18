/**
 * TanStack Query hooks for exception-related endpoints
 * 
 * Provides hooks for:
 * - Listing exceptions with filters and pagination
 * - Getting exception detail
 * - Getting exception evidence
 * - Getting exception audit trail
 * 
 * All hooks include tenantId in query keys and handle errors via snackbar.
 */

import { useQuery, useMutation, useQueryClient, UseQueryResult } from '@tanstack/react-query'
import { useTenant } from './useTenant'
import { getApiKeyForHttpClient, getTenantIdForHttpClient } from '../utils/httpClient'
import {
  listExceptions,
  getExceptionDetail,
  getExceptionEvidence,
  getExceptionAudit,
  fetchExceptionEvents,
  getExceptionPlaybook,
  recalculatePlaybook,
  completePlaybookStep,
  reprocessException,
  type ListExceptionsParams,
  type ListExceptionEventsParams,
  type ExceptionEventsListResponse,
  type PlaybookStatusResponse,
  type PlaybookRecalculationResponse,
  type StepCompletionRequest,
} from '../api/exceptions'
import type {
  ExceptionSummary,
  ExceptionDetailResponse,
  EvidenceResponse,
  AuditResponse,
  PaginatedResponse,
} from '../types'

/**
 * Query key factory for exception-related queries
 */
export const exceptionKeys = {
  /** All exception queries */
  all: ['exceptions'] as const,
  /** Exception list queries */
  lists: () => [...exceptionKeys.all, 'list'] as const,
  /** Exception list query with params */
  list: (tenantId: string | null, params?: ListExceptionsParams) =>
    [...exceptionKeys.lists(), tenantId, params] as const,
  /** Exception detail queries */
  details: () => [...exceptionKeys.all, 'detail'] as const,
  /** Exception detail query */
  detail: (tenantId: string | null, id: string) =>
    [...exceptionKeys.details(), tenantId, id] as const,
  /** Exception evidence queries */
  evidences: () => [...exceptionKeys.all, 'evidence'] as const,
  /** Exception evidence query */
  evidence: (tenantId: string | null, id: string) =>
    [...exceptionKeys.evidences(), tenantId, id] as const,
  /** Exception audit queries */
  audits: () => [...exceptionKeys.all, 'audit'] as const,
  /** Exception audit query */
  audit: (tenantId: string | null, id: string) =>
    [...exceptionKeys.audits(), tenantId, id] as const,
  /** Exception events queries */
  events: () => [...exceptionKeys.all, 'events'] as const,
  /** Exception events query */
  eventsList: (tenantId: string | null, exceptionId: string, params?: ListExceptionEventsParams) =>
    [...exceptionKeys.events(), tenantId, exceptionId, params] as const,
  /** Exception playbook queries */
  playbooks: () => [...exceptionKeys.all, 'playbook'] as const,
  /** Exception playbook query */
  playbook: (tenantId: string | null, exceptionId: string) =>
    [...exceptionKeys.playbooks(), tenantId, exceptionId] as const,
}

/**
 * Hook to fetch paginated list of exceptions
 * 
 * P6-26: Updated to use DB-backed /exceptions/{tenant_id} endpoint
 * 
 * @param params Optional filter and pagination parameters
 * @returns Query result with exception list data
 */
export function useExceptionsList(
  params?: ListExceptionsParams
): UseQueryResult<PaginatedResponse<ExceptionSummary>, Error> {
  const { tenantId, apiKey } = useTenant()
  // Also check httpClient directly as fallback
  const apiKeyFromHttpClient = getApiKeyForHttpClient()
  const tenantIdFromHttpClient = getTenantIdForHttpClient()
  const hasApiKey = !!(apiKey || apiKeyFromHttpClient)
  const effectiveTenantId = tenantId || tenantIdFromHttpClient

  return useQuery({
    queryKey: exceptionKeys.list(effectiveTenantId, params),
    queryFn: () => {
      if (!effectiveTenantId) {
        throw new Error('tenantId is required for listExceptions')
      }
      return listExceptions(effectiveTenantId, params)
    },
    enabled: !!effectiveTenantId && hasApiKey, // Only fetch if tenantId AND API key are set
    staleTime: 30_000, // 30 seconds
  })
}

/**
 * Hook to fetch exception detail with agent decisions
 * 
 * @param id Exception identifier
 * @returns Query result with exception detail
 */
export function useExceptionDetail(
  id: string
): UseQueryResult<ExceptionDetailResponse, Error> {
  const { tenantId, apiKey } = useTenant()
  const apiKeyFromHttpClient = getApiKeyForHttpClient()
  const tenantIdFromHttpClient = getTenantIdForHttpClient()
  const hasApiKey = !!(apiKey || apiKeyFromHttpClient)
  // Ensure tenantId is set in both React context AND httpClient before enabling query
  const hasTenantId = !!(tenantId || tenantIdFromHttpClient)

  return useQuery({
    queryKey: exceptionKeys.detail(tenantId, id),
    queryFn: () => getExceptionDetail(id),
    enabled: hasTenantId && !!id && hasApiKey, // Only fetch if tenantId, id, and API key are set
    staleTime: 60_000, // 1 minute (detail data changes less frequently)
    retry: (failureCount, error) => {
      // Don't retry on 404 errors (exception not found)
      if (error && (error as any).message?.includes('404')) {
        return false
      }
      // Don't retry on 400 errors (bad request, likely missing tenant_id)
      if (error && (error as any).status === 400) {
        // Only retry once for 400 errors in case tenantId wasn't set yet
        return failureCount < 1
      }
      // Retry up to 2 times for other errors (network issues, etc.)
      return failureCount < 2
    },
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 3000), // Exponential backoff
  })
}

/**
 * Hook to fetch exception evidence chains
 * 
 * @param id Exception identifier
 * @returns Query result with evidence data
 */
export function useExceptionEvidence(
  id: string
): UseQueryResult<EvidenceResponse, Error> {
  const { tenantId, apiKey } = useTenant()
  const apiKeyFromHttpClient = getApiKeyForHttpClient()
  const hasApiKey = !!(apiKey || apiKeyFromHttpClient)

  return useQuery({
    queryKey: exceptionKeys.evidence(tenantId, id),
    queryFn: () => getExceptionEvidence(id),
    enabled: !!tenantId && !!id && hasApiKey,
    staleTime: 60_000, // 1 minute
  })
}

/**
 * Hook to fetch exception audit trail
 * 
 * @param id Exception identifier
 * @returns Query result with audit events
 */
export function useExceptionAudit(
  id: string
): UseQueryResult<AuditResponse, Error> {
  const { tenantId, apiKey } = useTenant()
  const apiKeyFromHttpClient = getApiKeyForHttpClient()
  const hasApiKey = !!(apiKey || apiKeyFromHttpClient)

  return useQuery({
    queryKey: exceptionKeys.audit(tenantId, id),
    queryFn: () => getExceptionAudit(id),
    enabled: !!tenantId && !!id && hasApiKey,
    staleTime: 30_000, // 30 seconds (audit trail may update)
  })
}

/**
 * Hook to fetch exception events timeline
 * 
 * P6-27: New hook for fetching exception events with filtering and pagination
 * 
 * @param exceptionId Exception identifier
 * @param params Optional filter and pagination parameters (tenantId is required)
 * @returns Query result with exception events list
 */
export function useExceptionEvents(
  exceptionId: string,
  params?: Omit<ListExceptionEventsParams, 'tenantId'>
): UseQueryResult<ExceptionEventsListResponse, Error> {
  const { tenantId, apiKey } = useTenant()
  const tenantIdFromHttpClient = getTenantIdForHttpClient()
  const apiKeyFromHttpClient = getApiKeyForHttpClient()
  const hasApiKey = !!(apiKey || apiKeyFromHttpClient)
  const effectiveTenantId = tenantId || tenantIdFromHttpClient

  return useQuery({
    queryKey: exceptionKeys.eventsList(effectiveTenantId, exceptionId, params ? { ...params, tenantId: effectiveTenantId || '' } : undefined),
    queryFn: () => {
      if (!effectiveTenantId) {
        throw new Error('tenantId is required for fetchExceptionEvents')
      }
      return fetchExceptionEvents(exceptionId, {
        ...params,
        tenantId: effectiveTenantId,
      })
    },
    enabled: !!effectiveTenantId && !!exceptionId && hasApiKey,
    staleTime: 30_000, // 30 seconds (events may update)
  })
}

/**
 * Hook to fetch playbook status for an exception
 * 
 * Phase 7 P7-15: Returns playbook metadata and step statuses.
 * 
 * @param exceptionId Exception identifier
 * @returns Query result with playbook status
 */
export function useExceptionPlaybook(
  exceptionId: string
): UseQueryResult<PlaybookStatusResponse, Error> {
  const { tenantId, apiKey } = useTenant()
  const apiKeyFromHttpClient = getApiKeyForHttpClient()
  const tenantIdFromHttpClient = getTenantIdForHttpClient()
  const hasApiKey = !!(apiKey || apiKeyFromHttpClient)
  const effectiveTenantId = tenantId || tenantIdFromHttpClient

  return useQuery({
    queryKey: exceptionKeys.playbook(effectiveTenantId, exceptionId),
    queryFn: () => getExceptionPlaybook(exceptionId),
    enabled: !!effectiveTenantId && !!exceptionId && hasApiKey,
    staleTime: 30_000, // 30 seconds (playbook status may update)
  })
}

/**
 * Hook to recalculate playbook assignment for an exception
 * 
 * Phase 7 P7-16: Re-runs playbook matching and updates exception playbook assignment.
 * Automatically refetches playbook status after successful recalculation.
 * 
 * @param exceptionId Exception identifier
 * @returns Mutation object with mutate function and status
 */
export function useRecalculatePlaybook(exceptionId: string) {
  const queryClient = useQueryClient()
  const { tenantId } = useTenant()
  const apiKeyFromHttpClient = getApiKeyForHttpClient()
  const hasApiKey = !!apiKeyFromHttpClient

  return useMutation({
    mutationFn: () => recalculatePlaybook(exceptionId),
    onSuccess: () => {
      // Invalidate and refetch playbook status after successful recalculation
      queryClient.invalidateQueries({
        queryKey: exceptionKeys.playbook(tenantId, exceptionId),
      })
      // Phase 7 P7-18: Invalidate timeline events to refresh the timeline
      // (in case recalculation triggers events or user wants to see updated state)
      queryClient.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey
          // Match event queries for this exception
          return (
            key[0] === 'exceptions' &&
            key[1] === 'events' &&
            key[2] === tenantId &&
            key[3] === exceptionId
          )
        },
      })
    },
  })
}

/**
 * Hook to complete a playbook step for an exception
 * 
 * Phase 7 P7-17: Completes a playbook step and returns updated playbook status.
 * Automatically refetches playbook status and timeline after successful completion.
 * 
 * @param exceptionId Exception identifier
 * @returns Mutation object with mutate function and status
 */
export function useCompletePlaybookStep(exceptionId: string) {
  const queryClient = useQueryClient()
  const { tenantId } = useTenant()

  return useMutation({
    mutationFn: (params: { stepOrder: number; request: StepCompletionRequest }) =>
      completePlaybookStep(exceptionId, params.stepOrder, params.request),
    onSuccess: () => {
      // Invalidate and refetch playbook status after successful step completion
      queryClient.invalidateQueries({
        queryKey: exceptionKeys.playbook(tenantId, exceptionId),
      })
      // Invalidate timeline events to refresh the timeline
      // Invalidate all event queries for this exception (regardless of filter params)
      queryClient.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey
          // Match event queries for this exception
          return (
            key[0] === 'exceptions' &&
            key[1] === 'events' &&
            key[2] === tenantId &&
            key[3] === exceptionId
          )
        },
      })
    },
  })
}

/**
 * Hook to reprocess an existing exception through the pipeline
 * 
 * Manually triggers processing for an exception that exists in the database
 * but hasn't been processed through the pipeline.
 * 
 * @param exceptionId Exception identifier
 * @returns Mutation object with mutate function and status
 */
export function useReprocessException(exceptionId: string) {
  const queryClient = useQueryClient()
  const { tenantId } = useTenant()

  return useMutation({
    mutationFn: () => reprocessException(exceptionId),
    onSuccess: () => {
      // Invalidate all exception-related queries to refresh data
      queryClient.invalidateQueries({
        queryKey: exceptionKeys.detail(tenantId, exceptionId),
      })
      queryClient.invalidateQueries({
        queryKey: exceptionKeys.evidence(tenantId, exceptionId),
      })
      queryClient.invalidateQueries({
        queryKey: exceptionKeys.audit(tenantId, exceptionId),
      })
      queryClient.invalidateQueries({
        queryKey: exceptionKeys.playbook(tenantId, exceptionId),
      })
      // Invalidate timeline events
      queryClient.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey
          return (
            key[0] === 'exceptions' &&
            (key[1] === 'events' || key[1] === 'detail' || key[1] === 'evidence' || key[1] === 'audit') &&
            key[2] === tenantId &&
            key[3] === exceptionId
          )
        },
      })
    },
  })
}

