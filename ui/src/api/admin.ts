/**
 * Admin API client
 * 
 * Provides access to admin and governance endpoints from Phase 10.
 * All requests automatically include tenant context via httpClient interceptors.
 */

import { httpClient } from '../utils/httpClient'

// ============================================================================
// Types
// ============================================================================

export interface ConfigChangeRequest {
  id: string
  tenantId: string
  changeType: 'domain_pack' | 'policy_pack' | 'tool' | 'playbook'
  resourceId: string
  currentVersion?: string
  proposedConfig: Record<string, unknown>
  diffSummary?: Record<string, unknown>
  status: 'pending' | 'approved' | 'rejected' | 'applied'
  requestedBy: string
  requestedAt: string
  reviewedBy?: string
  reviewedAt?: string
  reviewComment?: string
  appliedAt?: string
}

export interface ConfigChangeListResponse {
  items: ConfigChangeRequest[]
  total: number
}

export interface ConfigChangeDiff {
  additions: Record<string, unknown>
  deletions: Record<string, unknown>
  changes: Record<string, { old: unknown; new: unknown }>
}

export interface RateLimitConfig {
  tenantId: string
  limitType: 'api_requests' | 'events_ingested' | 'tool_executions' | 'report_generations'
  limitValue: number
  windowSeconds: number
  enabled: boolean
}

export interface RateLimitUsage {
  tenantId: string
  limitType: string
  currentCount: number
  limitValue: number
  windowStart: string
  resetAt: string
}

export interface RateLimitUsageResponse {
  usage: RateLimitUsage[]
}

export interface DomainPack {
  id: string
  name: string
  version: string
  domain: string
  tenantId?: string
  config: Record<string, unknown>
  createdAt: string
  isActive?: boolean
}

export interface TenantPack {
  id: string
  name: string
  version: string
  tenantId: string
  domain: string
  config: Record<string, unknown>
  createdAt: string
  isActive?: boolean
}

export interface Playbook {
  id: string
  name: string
  version: string
  tenantId: string
  domain: string
  exceptionType: string
  matchRules: Record<string, unknown>
  steps: Array<Record<string, unknown>>
  referencedTools: string[]
  isActive: boolean
  createdAt: string
}

export interface PlaybookRegistryEntry {
  playbook_id: string
  name: string
  description?: string
  exception_type?: string
  domain: string
  version: string
  status: string
  source_pack_type: 'domain' | 'tenant'
  source_pack_id: number
  source_pack_version: string
  steps_count: number
  tool_refs_count: number
  overridden: boolean
  overridden_from?: string
}

export interface PlaybookRegistryParams {
  tenant_id?: string
  domain?: string
  exception_type?: string
  source?: 'domain' | 'tenant'
  search?: string
  page?: number
  page_size?: number
}

export interface PlaybookRegistryResponse {
  items: PlaybookRegistryEntry[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface Tool {
  id: string
  name: string
  description: string
  provider: string
  schema: Record<string, unknown>
  allowedTenants: string[]
  enabledForTenant?: boolean
}

// ============================================================================
// Config Change Governance API
// ============================================================================

export interface ListConfigChangesParams {
  tenantId?: string
  status?: 'pending' | 'approved' | 'rejected' | 'applied'
  changeType?: string
  limit?: number
  offset?: number
}

export async function listConfigChanges(params: ListConfigChangesParams = {}): Promise<ConfigChangeListResponse> {
  const response = await httpClient.get<{
    items: any[]
    total: number
    page?: number
    page_size?: number
  }>('/admin/config-changes', {
    params: {
      tenant_id: params.tenantId,
      status: params.status,
      change_type: params.changeType,
      page: params.offset ? Math.floor((params.offset || 0) / (params.limit || 100)) + 1 : 1,
      page_size: params.limit || 100,
    },
  })

  return {
    items: (response.items || []).map((item: any) => ({
      id: item.id,
      tenantId: item.tenant_id || item.tenantId || '',
      changeType: item.change_type || item.changeType,
      resourceId: item.resource_id || item.resourceId || '',
      currentVersion: item.current_version || item.currentVersion,
      proposedConfig: item.proposed_config || item.proposedConfig || {},
      diffSummary: item.diff_summary || item.diffSummary,
      status: item.status || 'pending',
      requestedBy: item.requested_by || item.requestedBy || '',
      requestedAt: item.requested_at || item.requestedAt || '',
      reviewedBy: item.reviewed_by || item.reviewedBy,
      reviewedAt: item.reviewed_at || item.reviewedAt,
      reviewComment: item.review_comment || item.reviewComment,
      appliedAt: item.applied_at || item.appliedAt,
    })),
    total: response.total || 0,
  }
}

export async function getConfigChange(id: string, tenantId: string): Promise<ConfigChangeRequest> {
  const response = await httpClient.get<any>(`/admin/config-changes/${id}`, {
    params: { tenant_id: tenantId },
  })

  return {
    id: response.id || id,
    tenantId: response.tenant_id || response.tenantId || tenantId,
    changeType: response.change_type || response.changeType,
    resourceId: response.resource_id || response.resourceId || '',
    currentVersion: response.current_version || response.currentVersion,
    proposedConfig: response.proposed_config || response.proposedConfig || {},
    diffSummary: response.diff_summary || response.diffSummary,
    status: response.status || 'pending',
    requestedBy: response.requested_by || response.requestedBy || '',
    requestedAt: response.requested_at || response.requestedAt || '',
    reviewedBy: response.reviewed_by || response.reviewedBy,
    reviewedAt: response.reviewed_at || response.reviewedAt,
    reviewComment: response.review_comment || response.reviewComment,
    appliedAt: response.applied_at || response.appliedAt,
  }
}

export async function getConfigChangeDiff(id: string, tenantId: string): Promise<ConfigChangeDiff> {
  const response = await httpClient.get<any>(`/admin/config-changes/${id}/diff`, {
    params: { tenant_id: tenantId },
  })

  return {
    additions: response.additions || {},
    deletions: response.deletions || {},
    changes: response.changes || {},
  }
}

export async function approveConfigChange(id: string, tenantId: string, comment?: string): Promise<void> {
  await httpClient.post(`/admin/config-changes/${id}/approve`, { comment }, {
    params: { tenant_id: tenantId },
  })
}

export async function rejectConfigChange(id: string, tenantId: string, comment: string): Promise<void> {
  await httpClient.post(`/admin/config-changes/${id}/reject`, { comment }, {
    params: { tenant_id: tenantId },
  })
}

// ============================================================================
// Rate Limits API
// ============================================================================

export async function getRateLimits(tenantId: string): Promise<RateLimitConfig[]> {
  const response = await httpClient.get<{
    tenant_id: string
    configs: Array<{
      tenant_id: string
      limit_type: string
      limit_value: number
      window_seconds: number
      enabled: boolean
      created_at: string
      updated_at: string
    }>
    defaults: Record<string, any>
  }>(`/admin/rate-limits/${tenantId}`)

  // Map configs from backend
  const configs = (response.configs || []).map((limit: any) => ({
    tenantId: limit.tenant_id || limit.tenantId || tenantId,
    limitType: limit.limit_type || limit.limitType,
    limitValue: limit.limit_value || limit.limitValue || 0,
    windowSeconds: limit.window_seconds || limit.windowSeconds || 60,
    enabled: limit.enabled !== false,
  }))

  // Add defaults for limit types not in configs
  if (response.defaults) {
    Object.entries(response.defaults).forEach(([limitType, defaultConfig]: [string, any]) => {
      if (!configs.find(c => c.limitType === limitType)) {
        configs.push({
          tenantId,
          limitType,
          limitValue: defaultConfig.limit_value || defaultConfig.limit || 0,
          windowSeconds: defaultConfig.window_seconds || defaultConfig.window || 60,
          enabled: defaultConfig.enabled !== false,
        })
      }
    })
  }

  return configs
}

export async function updateRateLimit(tenantId: string, limit: Partial<RateLimitConfig>): Promise<RateLimitConfig> {
  const response = await httpClient.put<{
    tenant_id: string
    limit_type: string
    limit_value: number
    window_seconds: number
    enabled: boolean
    created_at: string
    updated_at: string
  }>(`/admin/rate-limits/${tenantId}`, {
    limit_type: limit.limitType,
    limit_value: limit.limitValue || 0,
    window_seconds: limit.windowSeconds || 60,
    enabled: limit.enabled !== false,
  })

  return {
    tenantId: response.tenant_id || tenantId,
    limitType: response.limit_type,
    limitValue: response.limit_value,
    windowSeconds: response.window_seconds,
    enabled: response.enabled !== false,
  }
}

export async function getRateLimitUsage(tenantId: string): Promise<RateLimitUsageResponse> {
  const response = await httpClient.get<{
    tenant_id: string
    statuses: Array<{
      tenant_id: string
      limit_type: string
      limit: number
      current: number
      remaining: number
      window_seconds: number
      reset_at: string
      enabled: boolean
    }>
  }>('/usage/rate-limits', {
    params: { tenant_id: tenantId },
  })

  return {
    usage: (response.statuses || []).map((u: any) => ({
      tenantId: u.tenant_id || u.tenantId || tenantId,
      limitType: u.limit_type || u.limitType || '',
      currentCount: u.current || u.currentCount || 0,
      limitValue: u.limit || u.limitValue || 0,
      windowStart: u.window_start || '',
      resetAt: u.reset_at || u.resetAt || '',
    })),
  }
}

// ============================================================================
// Packs API
// ============================================================================

export interface ListPacksParams {
  tenantId?: string
  domain?: string
  limit?: number
  offset?: number
}

export async function listDomainPacks(params: ListPacksParams = {}): Promise<{ items: DomainPack[]; total: number }> {
  const response = await httpClient.get<{
    items: any[]
    total: number
  }>('/admin/config/domain-packs', {
    params: {
      tenant_id: params.tenantId,
      domain: params.domain,
      limit: params.limit || 100,
      offset: params.offset || 0,
    },
  })

  return {
    items: (response.items || []).map((item: any) => ({
      id: item.id || item.config_id || '',
      name: item.name || '',
      version: item.version || '',
      domain: item.domain || '',
      tenantId: item.tenant_id || item.tenantId,
      config: item.config || item.content || {},
      createdAt: item.created_at || item.createdAt || '',
      isActive: item.is_active || item.isActive,
    })),
    total: response.total || 0,
  }
}

export async function getDomainPack(id: string): Promise<DomainPack> {
  const response = await httpClient.get<any>(`/admin/config/domain-packs/${id}`)

  return {
    id: response.id || id,
    name: response.data?.domain_name || response.name || '',
    version: response.data?.version || response.version || '',
    domain: response.data?.domain_name || response.domain || '',
    tenantId: response.tenant_id || response.data?.tenant_id,
    config: response.data || response.config || {},
    createdAt: response.timestamp || response.created_at || '',
    isActive: response.is_active !== undefined ? response.is_active : undefined,
  }
}

export async function listTenantPacks(params: ListPacksParams = {}): Promise<{ items: TenantPack[]; total: number }> {
  const response = await httpClient.get<{
    items: any[]
    total: number
  }>('/admin/config/tenant-policies', {
    params: {
      tenant_id: params.tenantId,
      domain: params.domain,
      limit: params.limit || 100,
      offset: params.offset || 0,
    },
  })

  return {
    items: (response.items || []).map((item: any) => ({
      id: item.id || item.config_id || '',
      name: item.name || '',
      version: item.version || '',
      tenantId: item.tenant_id || item.tenantId || params.tenantId || '',
      domain: item.domain || '',
      config: item.config || item.content || {},
      createdAt: item.created_at || item.createdAt || '',
      isActive: item.is_active || item.isActive,
    })),
    total: response.total || 0,
  }
}

export async function getTenantPack(id: string): Promise<TenantPack> {
  const response = await httpClient.get<any>(`/admin/config/tenant-policies/${id}`)

  return {
    id: response.id || id,
    name: response.data?.tenant_id || response.name || '',
    version: response.data?.version || response.version || '',
    tenantId: response.tenant_id || response.data?.tenant_id || '',
    domain: response.data?.domain_name || response.domain || '',
    config: response.data || response.config || {},
    createdAt: response.timestamp || response.created_at || '',
    isActive: response.is_active !== undefined ? response.is_active : undefined,
  }
}

export async function activatePackVersion(packType: 'domain' | 'tenant', packId: string, version: string, tenantId: string): Promise<void> {
  const endpoint = packType === 'domain' 
    ? `/admin/config/domain-packs/${packId}/activate`
    : `/admin/config/tenant-policies/${packId}/activate`
  
  await httpClient.post(endpoint, { version }, {
    params: { tenant_id: tenantId },
  })
}

// ============================================================================
// Playbooks API
// ============================================================================

export interface ListPlaybooksParams {
  tenantId?: string
  domain?: string
  exceptionType?: string
  limit?: number
  offset?: number
}

export async function listPlaybooks(params: ListPlaybooksParams = {}): Promise<{ items: Playbook[]; total: number }> {
  const response = await httpClient.get<{
    items: any[]
    total: number
  }>('/admin/config/playbooks', {
    params: {
      tenant_id: params.tenantId,
      domain: params.domain,
      exception_type: params.exceptionType,
      limit: params.limit || 100,
      offset: params.offset || 0,
    },
  })

  return {
    items: (response.items || []).map((item: any) => ({
      id: item.id || item.config_id || '',
      name: item.name || '',
      version: item.version || '',
      tenantId: item.tenant_id || item.tenantId || '',
      domain: item.domain || '',
      exceptionType: item.exception_type || item.exceptionType || '',
      matchRules: item.match_rules || item.matchRules || {},
      steps: item.steps || [],
      referencedTools: item.referenced_tools || item.referencedTools || [],
      isActive: item.is_active || item.isActive !== false,
      createdAt: item.created_at || item.createdAt || '',
    })),
    total: response.total || 0,
  }
}

export async function getPlaybook(id: string): Promise<Playbook> {
  const response = await httpClient.get<any>(`/admin/config/playbooks/${id}`)

  // Extract data from ConfigDetailResponse format
  const data = response.data || response

  return {
    id: response.id || id,
    name: data.name || '',
    version: data.version || '',
    tenantId: response.tenant_id || data.tenant_id || '',
    domain: data.domain_name || data.domain || '',
    exceptionType: data.exception_type || '',
    matchRules: data.match_rules || data.matchRules || {},
    steps: data.steps || [],
    referencedTools: data.referenced_tools || data.referencedTools || [],
    isActive: data.is_active !== undefined ? data.is_active : true,
    createdAt: response.timestamp || data.created_at || '',
  }
}

export async function activatePlaybook(id: string, tenantId: string, active: boolean): Promise<void> {
  await httpClient.post(`/admin/config/playbooks/${id}/activate`, { active }, {
    params: { tenant_id: tenantId },
  })
}

export async function getPlaybooksRegistry(params: PlaybookRegistryParams = {}): Promise<PlaybookRegistryResponse> {
  const response = await httpClient.get<PlaybookRegistryResponse>('/admin/playbooks/registry', {
    params
  })
  return response
}

// ============================================================================
// Tools API
// ============================================================================

export interface ListToolsParams {
  tenantId?: string
  enabled?: boolean
  provider?: string
  limit?: number
  offset?: number
}

export async function listTools(params: ListToolsParams = {}): Promise<{ items: Tool[]; total: number }> {
  const response = await httpClient.get<{
    items: any[]
    total: number
  }>('/api/tools', {
    params: {
      tenant_id: params.tenantId,
      status: params.enabled === true ? 'enabled' : params.enabled === false ? 'disabled' : undefined,
      type: params.provider,
      page: params.offset ? Math.floor((params.offset || 0) / (params.limit || 100)) + 1 : 1,
      page_size: params.limit || 100,
    },
  })

  return {
    items: (response.items || []).map((item: any) => {
      // Extract schema from config if available
      const config = item.config || {}
      const schema = config.inputSchema || config.input_schema || config.parameters || {}
      
      return {
        id: String(item.toolId || item.tool_id || item.id || ''),
        name: item.name || '',
        description: config.description || item.description || '',
        provider: item.type || item.provider || '',
        schema: schema,
        allowedTenants: item.allowedTenants || item.allowed_tenants || [],
        enabledForTenant: item.enabled !== undefined ? item.enabled : undefined,
      }
    }),
    total: response.total || 0,
  }
}

export async function getTool(id: string): Promise<Tool> {
  const response = await httpClient.get<any>(`/api/tools/${id}`)

  // Extract schema from config if available
  const config = response.config || {}
  const schema = config.inputSchema || config.input_schema || config.parameters || {}

  return {
    id: String(response.toolId || response.tool_id || response.id || id),
    name: response.name || '',
    description: config.description || response.description || '',
    provider: response.type || response.provider || '',
    schema: schema,
    allowedTenants: response.allowedTenants || response.allowed_tenants || [],
    enabledForTenant: response.enabled !== undefined ? response.enabled : undefined,
  }
}

export async function enableToolForTenant(toolId: string, tenantId: string, enabled: boolean): Promise<void> {
  await httpClient.post(`/api/tools/${toolId}/enable`, { enabled }, {
    params: { tenant_id: tenantId },
  })
}

