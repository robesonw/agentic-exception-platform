/**
 * API client for exception-related endpoints
 * 
 * Mirrors backend routes from:
 * - src/api/routes/exceptions.py (P6-22: DB-backed API)
 * - src/api/routes/router_operator.py (UI detail endpoints)
 * 
 * All functions automatically include tenantId via httpClient interceptors.
 */

import { httpClient } from '../utils/httpClient'
import { getTenantIdForHttpClient } from '../utils/httpClient'
import type {
  ExceptionSummary,
  ExceptionDetailResponse,
  EvidenceResponse,
  AuditResponse,
  PaginatedResponse,
} from '../types'

/**
 * Parameters for listing exceptions
 * Mirrors query parameters from GET /exceptions/{tenant_id} in exceptions.py
 */
export interface ListExceptionsParams {
  /** Domain filter (optional) */
  domain?: string
  /** Resolution status filter (optional) - lowercase: open, analyzing, resolved, escalated */
  status?: string
  /** Severity filter (optional) - lowercase: low, medium, high, critical */
  severity?: string
  /** Start timestamp filter (optional, ISO datetime) */
  created_from?: string
  /** End timestamp filter (optional, ISO datetime) */
  created_to?: string
  /** Page number (1-indexed, default: 1) */
  page?: number
  /** Page size (default: 50, max: 100) */
  page_size?: number
}

/**
 * List exceptions with filtering and pagination
 * GET /exceptions/{tenant_id}
 * 
 * P6-22: Updated to use DB-backed endpoint instead of /ui/exceptions
 * 
 * @param tenantId Tenant identifier (required)
 * @param params Query parameters for filtering and pagination
 * @returns Paginated list of exception summaries
 */
export async function listExceptions(
  tenantId: string,
  params?: ListExceptionsParams
): Promise<PaginatedResponse<ExceptionSummary>> {
  if (!tenantId) {
    throw new Error('tenantId is required for listExceptions')
  }

  const response = await httpClient.get<{
    items: any[]
    total: number
    page: number
    page_size: number
    total_pages: number
  }>(`/exceptions/${tenantId}`, {
    params: {
      domain: params?.domain,
      status: params?.status,
      severity: params?.severity,
      created_from: params?.created_from,
      created_to: params?.created_to,
      page: params?.page || 1,
      page_size: params?.page_size || 50,
    },
  })
  
  // Transform backend response to frontend format
  // Backend returns ExceptionRecord.model_dump(by_alias=True), which uses camelCase
  const items: ExceptionSummary[] = (response.items || []).map((item: any) => {
    // Backend returns camelCase fields (exceptionId, tenantId, etc.) from ExceptionRecord
    // Map to frontend ExceptionSummary (snake_case for consistency with existing types)
    return {
      exception_id: item.exceptionId || item.exception_id || '',
      tenant_id: item.tenantId || item.tenant_id || tenantId,
      domain: item.normalizedContext?.domain || item.domain || null,
      exception_type: item.exceptionType || item.exception_type || null,
      severity: item.severity ? (typeof item.severity === 'string' ? item.severity.toUpperCase() : item.severity) : null,
      resolution_status: item.resolutionStatus || item.resolution_status || item.status || 'OPEN',
      source_system: item.sourceSystem || item.source_system || null,
      timestamp: item.timestamp || item.createdAt || item.created_at || new Date().toISOString(),
    } as ExceptionSummary
  })
  
  return {
    items,
    total: response.total || 0,
    page: response.page || 1,
    pageSize: response.page_size || response.pageSize || 50,
    totalPages: response.total_pages || response.totalPages || 1,
  }
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
  // tenant_id will be added automatically by httpClient interceptor
  // but we ensure it's explicitly passed in case interceptor hasn't run yet
  const tenantId = getTenantIdForHttpClient()
  if (!tenantId) {
    throw new Error('tenantId is required for getExceptionDetail')
  }
  return httpClient.get<ExceptionDetailResponse>(`/ui/exceptions/${exceptionId}`, {
    params: {
      tenant_id: tenantId,
    },
  })
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
  // tenant_id will be added automatically by httpClient interceptor
  // but we ensure it's explicitly passed in case interceptor hasn't run yet
  const tenantId = getTenantIdForHttpClient()
  if (!tenantId) {
    throw new Error('tenantId is required for getExceptionEvidence')
  }
  return httpClient.get<EvidenceResponse>(`/ui/exceptions/${exceptionId}/evidence`, {
    params: {
      tenant_id: tenantId,
    },
  })
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
  // tenant_id will be added automatically by httpClient interceptor
  // but we ensure it's explicitly passed in case interceptor hasn't run yet
  const tenantId = getTenantIdForHttpClient()
  if (!tenantId) {
    throw new Error('tenantId is required for getExceptionAudit')
  }
  return httpClient.get<AuditResponse>(`/ui/exceptions/${exceptionId}/audit`, {
    params: {
      tenant_id: tenantId,
    },
  })
}

/**
 * Parameters for fetching exception events
 * Mirrors query parameters from GET /exceptions/{exception_id}/events
 */
export interface ListExceptionEventsParams {
  /** Tenant identifier (required) */
  tenantId: string
  /** Event type filter (comma-separated list, optional) */
  eventType?: string
  /** Actor type filter (agent, user, system, optional) */
  actorType?: string
  /** Start date filter (ISO datetime, optional) */
  dateFrom?: string
  /** End date filter (ISO datetime, optional) */
  dateTo?: string
  /** Page number (1-indexed, default: 1) */
  page?: number
  /** Page size (default: 50, max: 100) */
  pageSize?: number
}

/**
 * Playbook step status
 * Mirrors PlaybookStepStatus from src/api/routes/exceptions.py
 */
export interface PlaybookStepStatus {
  /** Step order number (1-indexed) */
  stepOrder: number
  /** Step name */
  name: string
  /** Action type (e.g., notify, call_tool) */
  actionType: string
  /** Step status: pending, completed, or skipped */
  status: 'pending' | 'completed' | 'skipped'
}

/**
 * Playbook status response
 * Mirrors PlaybookStatusResponse from src/api/routes/exceptions.py
 */
export interface PlaybookStatusResponse {
  /** Exception identifier */
  exceptionId: string
  /** Playbook identifier (optional) */
  playbookId?: number | null
  /** Playbook name (optional) */
  playbookName?: string | null
  /** Playbook version (optional) */
  playbookVersion?: number | null
  /** Playbook matching conditions (optional) */
  conditions?: Record<string, unknown> | null
  /** List of playbook steps with status */
  steps: PlaybookStepStatus[]
  /** Current step number (1-indexed, optional) */
  currentStep?: number | null
}

/**
 * Playbook recalculation response
 * Mirrors PlaybookRecalculationResponse from src/api/routes/exceptions.py
 */
export interface PlaybookRecalculationResponse {
  /** Exception identifier */
  exceptionId: string
  /** Current playbook identifier (optional) */
  currentPlaybookId?: number | null
  /** Current step number in playbook (optional) */
  currentStep?: number | null
  /** Name of the selected playbook (optional) */
  playbookName?: string | null
  /** Version of the selected playbook (optional) */
  playbookVersion?: number | null
  /** Reasoning for playbook selection (optional) */
  reasoning?: string | null
}

/**
 * Step completion request
 * Mirrors StepCompletionRequest from src/api/routes/exceptions.py
 */
export interface StepCompletionRequest {
  /** Actor type: human, agent, or system */
  actorType: 'human' | 'agent' | 'system'
  /** Actor identifier (user ID or agent name) */
  actorId: string
  /** Optional notes about step completion */
  notes?: string | null
}

/**
 * Exception event structure
 * Mirrors response from GET /exceptions/{exception_id}/events
 */
export interface ExceptionEvent {
  /** Event identifier */
  eventId: string
  /** Exception identifier */
  exceptionId: string
  /** Tenant identifier */
  tenantId: string
  /** Event type (e.g., "ExceptionCreated", "TriageCompleted") */
  eventType: string
  /** Actor type (agent, user, system) */
  actorType: string
  /** Actor identifier (optional) */
  actorId?: string | null
  /** Event payload (JSON object) */
  payload: Record<string, unknown>
  /** Event timestamp (ISO datetime) */
  createdAt: string
}

/**
 * Exception events list response
 */
export interface ExceptionEventsListResponse {
  /** List of events */
  items: ExceptionEvent[]
  /** Total number of events */
  total: number
  /** Current page number (1-indexed) */
  page: number
  /** Page size */
  pageSize: number
  /** Total number of pages */
  totalPages: number
}

/**
 * Get event timeline for a specific exception
 * GET /exceptions/{exception_id}/events
 * 
 * P6-27: New endpoint for fetching exception events with filtering and pagination
 * 
 * @param exceptionId Exception identifier
 * @param params Query parameters including tenantId (required) and optional filters
 * @returns Paginated list of exception events in chronological order
 */
export async function fetchExceptionEvents(
  exceptionId: string,
  params: ListExceptionEventsParams
): Promise<ExceptionEventsListResponse> {
  if (!params.tenantId) {
    throw new Error('tenantId is required for fetchExceptionEvents')
  }

  const response = await httpClient.get<{
    items: any[]
    total: number
    page: number
    page_size: number
    total_pages: number
  }>(`/exceptions/${exceptionId}/events`, {
    params: {
      tenant_id: params.tenantId,
      event_type: params.eventType,
      actor_type: params.actorType,
      date_from: params.dateFrom,
      date_to: params.dateTo,
      page: params.page || 1,
      page_size: params.pageSize || 50,
    },
  })

  // Transform backend response to frontend format
  const items: ExceptionEvent[] = (response.items || []).map((item: any) => ({
    eventId: item.eventId || item.event_id || '',
    exceptionId: item.exceptionId || item.exception_id || exceptionId,
    tenantId: item.tenantId || item.tenant_id || params.tenantId,
    eventType: item.eventType || item.event_type || '',
    actorType: item.actorType || item.actor_type || '',
    actorId: item.actorId || item.actor_id || null,
    payload: item.payload || {},
    createdAt: item.createdAt || item.created_at || new Date().toISOString(),
  }))

  return {
    items,
    total: response.total || 0,
    page: response.page || 1,
    pageSize: response.page_size || response.pageSize || 50,
    totalPages: response.total_pages || response.totalPages || 1,
  }
}

/**
 * Get playbook status for an exception
 * GET /exceptions/{tenant_id}/{exception_id}/playbook
 * 
 * Phase 7 P7-15: Returns playbook metadata and step statuses.
 * 
 * @param exceptionId Exception identifier
 * @returns Playbook status with steps and current step indicator
 */
export async function getExceptionPlaybook(
  exceptionId: string
): Promise<PlaybookStatusResponse> {
  // tenant_id will be added automatically by httpClient interceptor
  // but we ensure it's explicitly passed in case interceptor hasn't run yet
  const tenantId = getTenantIdForHttpClient()
  if (!tenantId) {
    throw new Error('tenantId is required for getExceptionPlaybook')
  }
  
  // Backend endpoint is /exceptions/{tenant_id}/{exception_id}/playbook
  // Note: tenant_id is in the path, not as a query parameter
  const response = await httpClient.get<PlaybookStatusResponse>(
    `/exceptions/${tenantId}/${exceptionId}/playbook`
  )
  
  return response
}

/**
 * Recalculate playbook assignment for an exception
 * POST /exceptions/{tenant_id}/{exception_id}/playbook/recalculate
 * 
 * Phase 7 P7-16: Re-runs playbook matching and updates exception playbook assignment.
 * 
 * @param exceptionId Exception identifier
 * @returns Playbook recalculation response with updated assignment
 */
export async function recalculatePlaybook(
  exceptionId: string
): Promise<PlaybookRecalculationResponse> {
  // tenant_id will be added automatically by httpClient interceptor
  // but we ensure it's explicitly passed in case interceptor hasn't run yet
  const tenantId = getTenantIdForHttpClient()
  if (!tenantId) {
    throw new Error('tenantId is required for recalculatePlaybook')
  }
  
  // Backend endpoint is /exceptions/{tenant_id}/{exception_id}/playbook/recalculate
  // Note: tenant_id is in the path, not as a query parameter
  const response = await httpClient.post<PlaybookRecalculationResponse>(
    `/exceptions/${tenantId}/${exceptionId}/playbook/recalculate`
  )
  
  return response
}

/**
 * Complete a playbook step for an exception
 * POST /exceptions/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete
 * 
 * Phase 7 P7-17: Completes a playbook step and returns updated playbook status.
 * 
 * @param exceptionId Exception identifier
 * @param stepOrder Step order number to complete (1-indexed)
 * @param request Step completion request with actor type, actor ID, and optional notes
 * @returns Updated playbook status response
 */
export async function completePlaybookStep(
  exceptionId: string,
  stepOrder: number,
  request: StepCompletionRequest
): Promise<PlaybookStatusResponse> {
  // tenant_id will be added automatically by httpClient interceptor
  // but we ensure it's explicitly passed in case interceptor hasn't run yet
  const tenantId = getTenantIdForHttpClient()
  if (!tenantId) {
    throw new Error('tenantId is required for completePlaybookStep')
  }
  
  // Backend endpoint is /exceptions/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete
  // Note: tenant_id is in the path, not as a query parameter
  const response = await httpClient.post<PlaybookStatusResponse>(
    `/exceptions/${tenantId}/${exceptionId}/playbook/steps/${stepOrder}/complete`,
    request
  )
  
  return response
}

