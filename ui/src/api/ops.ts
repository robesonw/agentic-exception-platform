/**
 * Operations API client
 * 
 * Provides read-only access to operational data like Dead Letter Queue entries.
 * This API is typically hidden behind environment flags.
 */

import { httpClient } from '../utils/httpClient'

/**
 * DLQ entry structure
 */
export interface DLQEntry {
  /** Original event identifier */
  eventId: string
  /** Type of the original event */
  eventType: string
  /** Tenant identifier */
  tenantId: string
  /** Exception identifier (optional) */
  exceptionId?: string | null
  /** Original topic where event was published */
  originalTopic: string
  /** Reason for failure */
  failureReason: string
  /** Number of retry attempts made */
  retryCount: number
  /** Worker type that failed */
  workerType: string
  /** Original event payload */
  payload: Record<string, unknown>
  /** Event metadata */
  eventMetadata: Record<string, unknown>
  /** ISO datetime when event was moved to DLQ */
  failedAt: string
}

/**
 * DLQ list response
 */
export interface DLQListResponse {
  /** List of DLQ entries */
  items: DLQEntry[]
  /** Total number of DLQ entries matching filters */
  total: number
  /** Limit used for pagination */
  limit: number
  /** Offset used for pagination */
  offset: number
}

/**
 * Parameters for listing DLQ entries
 */
export interface ListDLQParams {
  /** Tenant identifier (required) */
  tenantId: string
  /** Status filter (reserved for future use) */
  status?: string
  /** Maximum number of results (1-1000, default: 100) */
  limit?: number
  /** Number of results to skip (default: 0) */
  offset?: number
}

/**
 * List Dead Letter Queue entries
 * GET /api/ops/dlq
 * 
 * @param params Query parameters including tenantId (required) and optional filters
 * @returns Paginated list of DLQ entries
 */
export async function listDLQEntries(params: ListDLQParams): Promise<DLQListResponse> {
  if (!params.tenantId) {
    throw new Error('tenantId is required for listDLQEntries')
  }

  const response = await httpClient.get<{
    items: any[]
    total: number
    limit: number
    offset: number
  }>('/ops/dlq', {
    params: {
      tenant_id: params.tenantId,
      status: params.status,
      limit: params.limit || 100,
      offset: params.offset || 0,
    },
  })

  // Transform backend response to frontend format
  const items: DLQEntry[] = (response.items || []).map((item: any) => ({
    eventId: item.event_id || item.eventId || '',
    eventType: item.event_type || item.eventType || '',
    tenantId: item.tenant_id || item.tenantId || params.tenantId,
    exceptionId: item.exception_id || item.exceptionId || null,
    originalTopic: item.original_topic || item.originalTopic || '',
    failureReason: item.failure_reason || item.failureReason || '',
    retryCount: item.retry_count || item.retryCount || 0,
    workerType: item.worker_type || item.workerType || '',
    payload: item.payload || {},
    eventMetadata: item.event_metadata || item.eventMetadata || {},
    failedAt: item.failed_at || item.failedAt || '',
  }))

  return {
    items,
    total: response.total || 0,
    limit: response.limit || 100,
    offset: response.offset || 0,
  }
}

