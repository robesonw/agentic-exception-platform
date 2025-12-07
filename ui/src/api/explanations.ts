/**
 * API client for explanation endpoints
 * 
 * Mirrors backend routes from:
 * - src/api/routes/router_explanations.py
 * 
 * All functions automatically include tenantId via httpClient interceptors.
 */

import { httpClient } from '../utils/httpClient'
import type {
  ExplanationResponse,
  ExplanationSearchResponse,
  DecisionTimeline,
  EvidenceGraph,
  ExplanationFormat,
} from '../types'

/**
 * Parameters for getting an explanation
 * Mirrors query parameters from GET /explanations/{exception_id}
 */
export interface GetExplanationParams {
  /** Output format (default: 'json') */
  format?: ExplanationFormat
}

/**
 * Parameters for searching explanations
 * Mirrors query parameters from GET /explanations/search
 */
export interface SearchExplanationsParams {
  /** Filter by agent name (optional) */
  agent_name?: string
  /** Filter by decision type (optional) */
  decision_type?: string
  /** Start timestamp filter (optional, ISO format) */
  from_ts?: string
  /** End timestamp filter (optional, ISO format) */
  to_ts?: string
  /** Text search query (optional) */
  text?: string
  /** Page number (1-indexed, default: 1) */
  page?: number
  /** Page size (default: 50, max: 100) */
  page_size?: number
}

/**
 * Get explanation for an exception
 * GET /explanations/{exception_id}
 * 
 * @param exceptionId Exception identifier
 * @param params Optional parameters (format)
 * @returns Explanation in requested format
 */
export async function getExplanation(
  exceptionId: string,
  params?: GetExplanationParams
): Promise<ExplanationResponse> {
  return httpClient.get<ExplanationResponse>(`/explanations/${exceptionId}`, {
    params: {
      format: params?.format ?? 'json',
    },
  })
}

/**
 * Get decision timeline for an exception
 * GET /explanations/{exception_id}/timeline
 * 
 * @param exceptionId Exception identifier
 * @returns Decision timeline with all events in chronological order
 */
export async function getTimeline(
  exceptionId: string
): Promise<DecisionTimeline> {
  return httpClient.get<DecisionTimeline>(`/explanations/${exceptionId}/timeline`)
}

/**
 * Get evidence graph for an exception
 * GET /explanations/{exception_id}/evidence
 * 
 * @param exceptionId Exception identifier
 * @returns Evidence graph with items, links, and graph structure
 */
export async function getEvidenceGraph(
  exceptionId: string
): Promise<EvidenceGraph> {
  return httpClient.get<EvidenceGraph>(`/explanations/${exceptionId}/evidence`)
}

/**
 * Search explanations with filters
 * GET /explanations/search
 * 
 * @param params Search parameters
 * @returns Paginated list of explanation summaries
 */
export async function searchExplanations(
  params?: SearchExplanationsParams
): Promise<ExplanationSearchResponse> {
  return httpClient.get<ExplanationSearchResponse>('/explanations/search', {
    params,
  })
}

