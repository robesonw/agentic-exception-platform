/**
 * TanStack Query hooks for explanation endpoints
 * 
 * Provides hooks for:
 * - Getting explanations in various formats
 * - Getting decision timelines
 * - Getting evidence graphs
 * - Searching explanations
 * 
 * All hooks include tenantId in query keys and handle errors via snackbar.
 */

import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { useTenant } from './useTenant'
import {
  getExplanation,
  getTimeline,
  getEvidenceGraph,
  searchExplanations,
  type GetExplanationParams,
  type SearchExplanationsParams,
} from '../api/explanations'
import type {
  ExplanationResponse,
  ExplanationSearchResponse,
  DecisionTimeline,
  EvidenceGraph,
} from '../types'

/**
 * Query key factory for explanation-related queries
 */
export const explanationKeys = {
  /** All explanation queries */
  all: ['explanations'] as const,
  /** Explanation detail queries */
  details: () => [...explanationKeys.all, 'detail'] as const,
  /** Explanation detail query */
  detail: (tenantId: string | null, id: string, format?: string) =>
    [...explanationKeys.details(), tenantId, id, format] as const,
  /** Timeline queries */
  timelines: () => [...explanationKeys.all, 'timeline'] as const,
  /** Timeline query */
  timeline: (tenantId: string | null, id: string) =>
    [...explanationKeys.timelines(), tenantId, id] as const,
  /** Evidence graph queries */
  evidenceGraphs: () => [...explanationKeys.all, 'evidence'] as const,
  /** Evidence graph query */
  evidenceGraph: (tenantId: string | null, id: string) =>
    [...explanationKeys.evidenceGraphs(), tenantId, id] as const,
  /** Explanation search queries */
  searches: () => [...explanationKeys.all, 'search'] as const,
  /** Explanation search query */
  search: (tenantId: string | null, params?: SearchExplanationsParams) =>
    [...explanationKeys.searches(), tenantId, params] as const,
}

/**
 * Hook to fetch explanation for an exception
 * 
 * @param id Exception identifier
 * @param params Optional parameters (format: 'json' | 'text' | 'structured')
 * @returns Query result with explanation in requested format
 */
export function useExplanation(
  id: string,
  params?: GetExplanationParams
): UseQueryResult<ExplanationResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: explanationKeys.detail(tenantId, id, params?.format),
    queryFn: () => getExplanation(id, params),
    enabled: !!tenantId && !!id,
    staleTime: 60_000, // 1 minute (explanations may update)
  })
}

/**
 * Hook to fetch decision timeline for an exception
 * 
 * @param id Exception identifier
 * @returns Query result with decision timeline
 */
export function useTimeline(
  id: string
): UseQueryResult<DecisionTimeline, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: explanationKeys.timeline(tenantId, id),
    queryFn: () => getTimeline(id),
    enabled: !!tenantId && !!id,
    staleTime: 60_000, // 1 minute
  })
}

/**
 * Hook to fetch evidence graph for an exception
 * 
 * @param id Exception identifier
 * @returns Query result with evidence graph
 */
export function useEvidenceGraph(
  id: string
): UseQueryResult<EvidenceGraph, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: explanationKeys.evidenceGraph(tenantId, id),
    queryFn: () => getEvidenceGraph(id),
    enabled: !!tenantId && !!id,
    staleTime: 60_000, // 1 minute
  })
}

/**
 * Hook to search explanations with filters
 * 
 * @param params Optional search parameters
 * @returns Query result with paginated explanation summaries
 */
export function useSearchExplanations(
  params?: SearchExplanationsParams
): UseQueryResult<ExplanationSearchResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: explanationKeys.search(tenantId, params),
    queryFn: () => searchExplanations(params),
    enabled: !!tenantId,
    staleTime: 30_000, // 30 seconds
  })
}

