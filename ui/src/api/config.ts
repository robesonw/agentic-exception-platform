/**
 * API client for configuration viewing endpoints
 * 
 * Mirrors backend routes from:
 * - src/api/routes/router_config_view.py
 * 
 * All functions automatically include tenantId via httpClient interceptors.
 */

import { httpClient } from '../utils/httpClient'
import type {
  ConfigListResponse,
  ConfigDetailResponse,
  ConfigDiffResponse,
  ConfigHistoryResponse,
  ConfigType,
  RollbackRequest,
  RollbackResponse,
  GuardrailRecommendationsResponse,
} from '../types'

/**
 * Parameters for listing domain packs
 * Mirrors query parameters from GET /admin/config/domain-packs
 */
export interface ListDomainPacksParams {
  /** Optional tenant filter */
  tenant_id?: string
  /** Optional domain filter */
  domain?: string
}

/**
 * Parameters for configuration diff
 * Mirrors query parameters from GET /admin/config/diff
 */
export interface ConfigDiffParams {
  /** Configuration type */
  type: ConfigType
  /** Left configuration ID */
  leftVersion: string
  /** Right configuration ID */
  rightVersion: string
}

/**
 * List domain packs
 * GET /admin/config/domain-packs
 * 
 * @param params Optional query parameters
 * @returns List of domain packs
 */
export async function listDomainPacks(
  params?: ListDomainPacksParams
): Promise<ConfigListResponse> {
  return httpClient.get<ConfigListResponse>('/admin/config/domain-packs', {
    params,
  })
}

/**
 * Get a specific domain pack by ID
 * GET /admin/config/domain-packs/{config_id}
 * 
 * @param configId Domain pack identifier (format: tenant_id:domain:version)
 * @returns Domain pack detail
 */
export async function getDomainPackDetail(
  configId: string
): Promise<ConfigDetailResponse> {
  return httpClient.get<ConfigDetailResponse>(`/admin/config/domain-packs/${configId}`)
}

/**
 * Get a specific tenant policy by ID
 * GET /admin/config/tenant-policies/{config_id}
 * 
 * Note: There is no list endpoint for tenant policies in the backend.
 * Use getTenantPolicyDetail with a known config_id.
 * 
 * @param configId Tenant policy identifier (format: tenant_id:domain)
 * @returns Tenant policy detail
 */
export async function getTenantPolicyDetail(
  configId: string
): Promise<ConfigDetailResponse> {
  return httpClient.get<ConfigDetailResponse>(`/admin/config/tenant-policies/${configId}`)
}

/**
 * Get a specific playbook by ID
 * GET /admin/config/playbooks/{config_id}
 * 
 * Note: There is no list endpoint for playbooks in the backend.
 * Use getPlaybookDetail with a known config_id.
 * 
 * @param configId Playbook identifier (format: tenant_id:domain:exception_type)
 * @returns Playbook detail
 */
export async function getPlaybookDetail(
  configId: string
): Promise<ConfigDetailResponse> {
  return httpClient.get<ConfigDetailResponse>(`/admin/config/playbooks/${configId}`)
}

/**
 * Diff two configurations
 * GET /admin/config/diff
 * 
 * @param params Diff parameters (type, leftVersion, rightVersion)
 * @returns Configuration diff with structured differences
 */
export async function getConfigDiff(
  params: ConfigDiffParams
): Promise<ConfigDiffResponse> {
  return httpClient.get<ConfigDiffResponse>('/admin/config/diff', {
    params: {
      type: params.type,
      leftVersion: params.leftVersion,
      rightVersion: params.rightVersion,
    },
  })
}

/**
 * Get version history for a configuration
 * GET /admin/config/history/{config_type}/{config_id}
 * 
 * @param configType Configuration type
 * @param configId Configuration identifier
 * @returns Configuration version history
 */
export async function getConfigHistory(
  configType: ConfigType,
  configId: string
): Promise<ConfigHistoryResponse> {
  return httpClient.get<ConfigHistoryResponse>(
    `/admin/config/history/${configType}/${configId}`
  )
}

/**
 * Rollback configuration to a previous version (stub in Phase 3)
 * POST /admin/config/rollback
 * 
 * @param request Rollback request
 * @returns Rollback response (validation only in Phase 3)
 */
export async function rollbackConfig(
  request: RollbackRequest
): Promise<RollbackResponse> {
  return httpClient.post<RollbackResponse>('/admin/config/rollback', request)
}

/**
 * Parameters for guardrail recommendations
 */
export interface GuardrailRecommendationsParams {
  /** Tenant identifier */
  tenantId: string
  /** Domain name */
  domain: string
  /** Optional guardrail ID filter */
  guardrailId?: string
}

/**
 * Get guardrail recommendations
 * GET /learning/guardrail-recommendations
 * 
 * @param params Recommendation parameters (tenantId, domain, optional guardrailId)
 * @returns Guardrail recommendations response
 */
export async function getGuardrailRecommendations(
  params: GuardrailRecommendationsParams
): Promise<GuardrailRecommendationsResponse> {
  return httpClient.get<GuardrailRecommendationsResponse>('/learning/guardrail-recommendations', {
    params: {
      tenant_id: params.tenantId,
      domain: params.domain,
      guardrail_id: params.guardrailId,
    },
  })
}

