/**
 * Phase 12+ Governance Audit API Client
 *
 * Provides access to governance audit event endpoints for:
 * - Querying audit events with filters
 * - Entity timeline views
 * - Recent changes queries
 *
 * Reference: Phase 12+ Governance & Audit Polish requirements
 */

import { httpClient } from '../utils/httpClient'

// ============================================================================
// Types
// ============================================================================

export interface GovernanceAuditEvent {
  id: string
  event_type: string
  actor_id: string
  actor_role?: string
  tenant_id?: string
  domain?: string
  entity_type: string
  entity_id: string
  entity_version?: string
  action: string
  before_json?: Record<string, unknown>
  after_json?: Record<string, unknown>
  diff_summary?: string
  correlation_id?: string
  request_id?: string
  related_exception_id?: string
  related_change_request_id?: string
  metadata?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface PaginatedAuditEventsResponse {
  items: GovernanceAuditEvent[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface EntityTimelineResponse {
  entity_type: string
  entity_id: string
  tenant_id?: string
  events: GovernanceAuditEvent[]
  total: number
}

export interface RecentChangesResponse {
  items: GovernanceAuditEvent[]
  total: number
}

export interface ListAuditEventsParams {
  tenant_id?: string
  domain?: string
  entity_type?: string
  entity_id?: string
  event_type?: string
  action?: string
  actor_id?: string
  correlation_id?: string
  from_date?: string
  to_date?: string
  page?: number
  page_size?: number
}

// ============================================================================
// Entity Types
// ============================================================================

export const ENTITY_TYPES = [
  'tenant',
  'domain_pack',
  'tenant_pack',
  'playbook',
  'tool',
  'rate_limit',
  'alert_config',
  'config_change',
  'active_config',
] as const

export type EntityType = (typeof ENTITY_TYPES)[number]

// ============================================================================
// Action Types
// ============================================================================

export const ACTIONS = [
  'create',
  'update',
  'delete',
  'import',
  'validate',
  'activate',
  'deprecate',
  'enable',
  'disable',
  'approve',
  'reject',
  'apply',
  'status_change',
  'link',
  'unlink',
] as const

export type ActionType = (typeof ACTIONS)[number]

// ============================================================================
// Event Types
// ============================================================================

export const EVENT_TYPES = [
  // Tenant events
  'TENANT_CREATED',
  'TENANT_UPDATED',
  'TENANT_STATUS_CHANGED',
  'TENANT_DELETED',
  // Domain pack events
  'DOMAIN_PACK_IMPORTED',
  'DOMAIN_PACK_UPDATED',
  'DOMAIN_PACK_VALIDATED',
  'DOMAIN_PACK_ACTIVATED',
  'DOMAIN_PACK_DEPRECATED',
  // Tenant pack events
  'TENANT_PACK_IMPORTED',
  'TENANT_PACK_UPDATED',
  'TENANT_PACK_VALIDATED',
  'TENANT_PACK_ACTIVATED',
  'TENANT_PACK_DEPRECATED',
  // Config events
  'CONFIG_ACTIVATED',
  'CONFIG_ACTIVATION_REQUESTED',
  // Playbook events
  'PLAYBOOK_CREATED',
  'PLAYBOOK_UPDATED',
  'PLAYBOOK_ACTIVATED',
  'PLAYBOOK_LINKED',
  'PLAYBOOK_UNLINKED',
  // Tool events
  'TOOL_CREATED',
  'TOOL_UPDATED',
  'TOOL_ENABLED',
  'TOOL_DISABLED',
  // Rate limit events
  'RATE_LIMIT_CREATED',
  'RATE_LIMIT_UPDATED',
  'RATE_LIMIT_DELETED',
  // Alert events
  'ALERT_CONFIG_CREATED',
  'ALERT_CONFIG_UPDATED',
  'ALERT_CONFIG_ENABLED',
  'ALERT_CONFIG_DISABLED',
  // Config change governance
  'CONFIG_CHANGE_SUBMITTED',
  'CONFIG_CHANGE_APPROVED',
  'CONFIG_CHANGE_REJECTED',
  'CONFIG_CHANGE_APPLIED',
] as const

export type EventType = (typeof EVENT_TYPES)[number]

// ============================================================================
// API Functions
// ============================================================================

/**
 * List audit events with filtering and pagination
 * GET /admin/audit/events
 */
export async function listAuditEvents(
  params: ListAuditEventsParams = {}
): Promise<PaginatedAuditEventsResponse> {
  return await httpClient.get<PaginatedAuditEventsResponse>('/admin/audit/events', {
    params: {
      tenant_id: params.tenant_id,
      domain: params.domain,
      entity_type: params.entity_type,
      entity_id: params.entity_id,
      event_type: params.event_type,
      action: params.action,
      actor_id: params.actor_id,
      correlation_id: params.correlation_id,
      from_date: params.from_date,
      to_date: params.to_date,
      page: params.page || 1,
      page_size: params.page_size || 50,
    },
  })
}

/**
 * Get a single audit event by ID
 * GET /admin/audit/events/{event_id}
 */
export async function getAuditEvent(eventId: string): Promise<GovernanceAuditEvent> {
  return await httpClient.get<GovernanceAuditEvent>(`/admin/audit/events/${eventId}`)
}

/**
 * Get entity timeline (all events for an entity)
 * GET /admin/audit/timeline
 */
export async function getEntityTimeline(
  entityType: string,
  entityId: string,
  tenantId?: string,
  limit: number = 50
): Promise<EntityTimelineResponse> {
  return await httpClient.get<EntityTimelineResponse>('/admin/audit/timeline', {
    params: {
      entity_type: entityType,
      entity_id: entityId,
      tenant_id: tenantId,
      limit,
    },
  })
}

/**
 * Get recent changes for a tenant
 * GET /admin/audit/recent/{tenant_id}
 */
export async function getRecentChangesByTenant(
  tenantId: string,
  entityTypes?: string[],
  limit: number = 20
): Promise<RecentChangesResponse> {
  return await httpClient.get<RecentChangesResponse>(`/admin/audit/recent/${tenantId}`, {
    params: {
      entity_types: entityTypes?.join(','),
      limit,
    },
  })
}

/**
 * Get recent changes for a specific entity
 * GET /admin/audit/entity/{entity_type}/{entity_id}/recent
 */
export async function getRecentChangesForEntity(
  entityType: string,
  entityId: string,
  tenantId?: string,
  limit: number = 5
): Promise<RecentChangesResponse> {
  return await httpClient.get<RecentChangesResponse>(
    `/admin/audit/entity/${entityType}/${entityId}/recent`,
    {
      params: {
        tenant_id: tenantId,
        limit,
      },
    }
  )
}

/**
 * Get events by correlation ID
 * GET /admin/audit/correlation/{correlation_id}
 */
export async function getEventsByCorrelation(
  correlationId: string
): Promise<GovernanceAuditEvent[]> {
  return await httpClient.get<GovernanceAuditEvent[]>(
    `/admin/audit/correlation/${correlationId}`
  )
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get a human-readable label for an entity type
 */
export function getEntityTypeLabel(entityType: string): string {
  const labels: Record<string, string> = {
    tenant: 'Tenant',
    domain_pack: 'Domain Pack',
    tenant_pack: 'Tenant Pack',
    playbook: 'Playbook',
    tool: 'Tool',
    rate_limit: 'Rate Limit',
    alert_config: 'Alert Config',
    config_change: 'Config Change',
    active_config: 'Active Config',
  }
  return labels[entityType] || entityType
}

/**
 * Get a human-readable label for an action
 */
export function getActionLabel(action: string): string {
  const labels: Record<string, string> = {
    create: 'Created',
    update: 'Updated',
    delete: 'Deleted',
    import: 'Imported',
    validate: 'Validated',
    activate: 'Activated',
    deprecate: 'Deprecated',
    enable: 'Enabled',
    disable: 'Disabled',
    approve: 'Approved',
    reject: 'Rejected',
    apply: 'Applied',
    status_change: 'Status Changed',
    link: 'Linked',
    unlink: 'Unlinked',
  }
  return labels[action] || action
}

/**
 * Get color for an action (for UI display)
 */
export function getActionColor(
  action: string
): 'success' | 'error' | 'warning' | 'info' | 'default' {
  const colors: Record<string, 'success' | 'error' | 'warning' | 'info' | 'default'> = {
    create: 'success',
    import: 'success',
    activate: 'success',
    enable: 'success',
    approve: 'success',
    apply: 'success',
    delete: 'error',
    disable: 'warning',
    deprecate: 'warning',
    reject: 'error',
    update: 'info',
    validate: 'info',
    status_change: 'info',
    link: 'info',
    unlink: 'warning',
  }
  return colors[action] || 'default'
}
