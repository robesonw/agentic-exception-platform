/**
 * API client for exception-related endpoints
 * 
 * Mirrors backend routes from:
 * - src/api/routes/router_operator.py
 * 
 * All functions automatically include tenantId via httpClient interceptors.
 */

import { httpClient } from '../utils/httpClient'
import type {
  ExceptionSummary,
  ExceptionDetailResponse,
  EvidenceResponse,
  AuditResponse,
  PaginatedResponse,
} from '../types'

/**
 * Parameters for listing exceptions
 * Mirrors query parameters from GET /ui/exceptions in router_operator.py
 */
export interface ListExceptionsParams {
  /** Domain filter (optional) */
  domain?: string
  /** Resolution status filter (optional) */
  status?: string
  /** Severity filter (optional) */
  severity?: string
  /** Start timestamp filter (optional, ISO format) */
  from_ts?: string
  /** End timestamp filter (optional, ISO format) */
  to_ts?: string
  /** Text search query (optional) */
  search?: string
  /** Page number (1-indexed, default: 1) */
  page?: number
  /** Page size (default: 50, max: 100) */
  page_size?: number
}

/**
 * List exceptions with filtering, search, and pagination
 * GET /ui/exceptions
 * 
 * @param params Query parameters for filtering and pagination
 * @returns Paginated list of exception summaries
 */
export async function listExceptions(
  params?: ListExceptionsParams
): Promise<PaginatedResponse<ExceptionSummary>> {
  const response = await httpClient.get<PaginatedResponse<ExceptionSummary> & { total_pages?: number }>('/ui/exceptions', {
    params,
  })
  
  // Transform snake_case to camelCase if needed
  if (response && typeof response === 'object' && response !== null && 'total_pages' in response && typeof (response as { total_pages?: number }).total_pages === 'number' && !('totalPages' in response)) {
    const responseWithTotalPages = response as PaginatedResponse<ExceptionSummary> & { total_pages: number }
    return {
      items: responseWithTotalPages.items,
      total: responseWithTotalPages.total,
      page: responseWithTotalPages.page,
      pageSize: responseWithTotalPages.pageSize,
      totalPages: responseWithTotalPages.total_pages,
    }
  }
  
  return response as PaginatedResponse<ExceptionSummary>
}

/**
 * Get full exception detail with agent decisions
 * GET /ui/exceptions/{exception_id}
 * 
 * @param exceptionId Exception identifier
 * @returns Full exception detail with agent decisions and pipeline result
 */
export async function getExceptionDetail(
  exceptionId: string
): Promise<ExceptionDetailResponse> {
  return httpClient.get<ExceptionDetailResponse>(`/ui/exceptions/${exceptionId}`)
}

/**
 * Get evidence chains for an exception
 * GET /ui/exceptions/{exception_id}/evidence
 * 
 * @param exceptionId Exception identifier
 * @returns Evidence response with RAG results, tool outputs, and agent evidence
 */
export async function getExceptionEvidence(
  exceptionId: string
): Promise<EvidenceResponse> {
  return httpClient.get<EvidenceResponse>(`/ui/exceptions/${exceptionId}/evidence`)
}

/**
 * Get audit events related to an exception
 * GET /ui/exceptions/{exception_id}/audit
 * 
 * @param exceptionId Exception identifier
 * @returns Audit response with list of audit events
 */
export async function getExceptionAudit(
  exceptionId: string
): Promise<AuditResponse> {
  return httpClient.get<AuditResponse>(`/ui/exceptions/${exceptionId}/audit`)
}

