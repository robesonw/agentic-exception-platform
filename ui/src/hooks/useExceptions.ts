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

import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { useTenant } from './useTenant'
import { getApiKeyForHttpClient, getTenantIdForHttpClient } from '../utils/httpClient'
import {
  listExceptions,
  getExceptionDetail,
  getExceptionEvidence,
  getExceptionAudit,
  type ListExceptionsParams,
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
}

/**
 * Hook to fetch paginated list of exceptions
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
  const hasApiKey = !!(apiKey || apiKeyFromHttpClient)

  return useQuery({
    queryKey: exceptionKeys.list(tenantId, params),
    queryFn: () => listExceptions(params),
    enabled: !!tenantId && hasApiKey, // Only fetch if tenantId AND API key are set
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

