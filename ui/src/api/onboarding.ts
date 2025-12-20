/**
 * Phase 12 Onboarding API Client
 * 
 * Provides access to Phase 12 tenant and pack onboarding endpoints.
 * All requests automatically include tenant context via httpClient interceptors.
 * 
 * Reference: docs/phase12-onboarding-packs-mvp.md
 */

import { httpClient } from '../utils/httpClient'

// ============================================================================
// Types
// ============================================================================

export interface Tenant {
  tenant_id: string
  name: string
  status: 'ACTIVE' | 'SUSPENDED'
  created_at: string
  created_by?: string
  updated_at: string
}

export interface TenantCreateRequest {
  tenant_id: string
  name: string
}

export interface TenantStatusUpdateRequest {
  status: 'ACTIVE' | 'SUSPENDED'
}

export interface PaginatedTenantResponse {
  items: Tenant[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface Pack {
  id: number
  domain?: string
  tenant_id?: string
  version: string
  status: 'DRAFT' | 'ACTIVE' | 'DEPRECATED'
  checksum: string
  created_at: string
  created_by: string
  content_json?: Record<string, unknown>
}

export interface PackImportRequest {
  domain?: string
  tenant_id?: string
  version: string
  content: Record<string, unknown>
}

export interface PackValidateRequest {
  pack_type: 'domain' | 'tenant'
  content: Record<string, unknown>
  domain?: string
}

export interface PackValidationResponse {
  is_valid: boolean
  errors: string[]
  warnings: string[]
}

export interface PaginatedPackResponse {
  items: Pack[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PackActivateRequest {
  tenant_id: string
  domain?: string
  domain_pack_version?: string
  tenant_pack_version?: string
  require_approval?: boolean
}

export interface PackActivateResponse {
  tenant_id: string
  active_domain_pack_version?: string
  active_tenant_pack_version?: string
  activated_at: string
  activated_by: string
  change_request_id?: string
}

export interface ActiveConfigResponse {
  tenant_id: string
  active_domain_pack_version?: string
  active_tenant_pack_version?: string
  activated_at: string
  activated_by: string
}

// ============================================================================
// Tenant Management API
// ============================================================================

export interface ListTenantsParams {
  page?: number
  page_size?: number
  status?: 'ACTIVE' | 'SUSPENDED'
}

/**
 * List tenants with pagination (P12-10)
 * GET /admin/tenants
 */
export async function listTenants(params: ListTenantsParams = {}): Promise<PaginatedTenantResponse> {
  const response = await httpClient.get<PaginatedTenantResponse>('/admin/tenants', {
    params: {
      page: params.page || 1,
      page_size: params.page_size || 50,
      status: params.status,
    },
  })
  return response
}

/**
 * Get tenant by ID (P12-10)
 * GET /admin/tenants/{tenant_id}
 */
export async function getTenant(tenantId: string): Promise<Tenant> {
  return await httpClient.get<Tenant>(`/admin/tenants/${tenantId}`)
}

/**
 * Create a new tenant (P12-10)
 * POST /admin/tenants
 */
export async function createTenant(request: TenantCreateRequest): Promise<Tenant> {
  return await httpClient.post<Tenant>('/admin/tenants', request)
}

/**
 * Update tenant status (P12-10)
 * PATCH /admin/tenants/{tenant_id}/status
 */
export async function updateTenantStatus(
  tenantId: string,
  request: TenantStatusUpdateRequest
): Promise<Tenant> {
  return await httpClient.patch<Tenant>(`/admin/tenants/${tenantId}/status`, request)
}

/**
 * Get active configuration for a tenant
 * GET /admin/tenants/{tenant_id}/active-config
 * Returns null if no active config exists (404)
 */
export async function getActiveConfig(tenantId: string): Promise<ActiveConfigResponse | null> {
  try {
    return await httpClient.get<ActiveConfigResponse>(`/admin/tenants/${tenantId}/active-config`)
  } catch (error: unknown) {
    // Handle 404 as expected case (no active config yet)
    if (error && typeof error === 'object' && 'status' in error && error.status === 404) {
      return null
    }
    throw error
  }
}

// ============================================================================
// Pack Import & Validation API
// ============================================================================

/**
 * Import a domain pack (P12-11)
 * POST /admin/packs/domain/import
 */
export async function importDomainPack(request: PackImportRequest): Promise<Pack> {
  if (!request.domain) {
    throw new Error('domain is required for domain pack import')
  }
  return await httpClient.post<Pack>('/admin/packs/domain/import', request)
}

/**
 * Import a tenant pack (P12-11)
 * POST /admin/packs/tenant/import
 */
export async function importTenantPack(request: PackImportRequest): Promise<Pack> {
  if (!request.tenant_id) {
    throw new Error('tenant_id is required for tenant pack import')
  }
  return await httpClient.post<Pack>('/admin/packs/tenant/import', request)
}

/**
 * Validate a pack without importing (P12-11)
 * POST /admin/packs/validate
 */
export async function validatePack(request: PackValidateRequest): Promise<PackValidationResponse> {
  return await httpClient.post<PackValidationResponse>('/admin/packs/validate', request)
}

// ============================================================================
// Pack Listing & Version API
// ============================================================================

export interface ListDomainPacksParams {
  domain?: string
  status?: 'DRAFT' | 'ACTIVE' | 'DEPRECATED'
  page?: number
  page_size?: number
}

/**
 * List domain packs with pagination (P12-12)
 * GET /admin/packs/domain
 */
export async function listDomainPacks(params: ListDomainPacksParams = {}): Promise<PaginatedPackResponse> {
  return await httpClient.get<PaginatedPackResponse>('/admin/packs/domain', {
    params: {
      domain: params.domain,
      status: params.status,
      page: params.page || 1,
      page_size: params.page_size || 50,
    },
  })
}

/**
 * Get domain pack by domain and version (P12-12)
 * GET /admin/packs/domain/{domain}/{version}
 */
export async function getDomainPack(domain: string, version: string): Promise<Pack> {
  return await httpClient.get<Pack>(`/admin/packs/domain/${domain}/${version}`)
}

export interface ListTenantPacksParams {
  tenant_id: string
  status?: 'DRAFT' | 'ACTIVE' | 'DEPRECATED'
  page?: number
  page_size?: number
}

/**
 * List tenant packs for a tenant (P12-12)
 * GET /admin/packs/tenant/{tenant_id}
 */
export async function listTenantPacks(params: ListTenantPacksParams): Promise<PaginatedPackResponse> {
  return await httpClient.get<PaginatedPackResponse>(`/admin/packs/tenant/${params.tenant_id}`, {
    params: {
      status: params.status,
      page: params.page || 1,
      page_size: params.page_size || 50,
    },
  })
}

/**
 * Get tenant pack by tenant and version (P12-12)
 * GET /admin/packs/tenant/{tenant_id}/{version}
 */
export async function getTenantPack(tenantId: string, version: string): Promise<Pack> {
  return await httpClient.get<Pack>(`/admin/packs/tenant/${tenantId}/${version}`)
}

// ============================================================================
// Pack Activation API
// ============================================================================

/**
 * Activate pack configuration for a tenant (P12-13)
 * POST /admin/packs/activate
 */
export async function activatePacks(request: PackActivateRequest): Promise<PackActivateResponse> {
  return await httpClient.post<PackActivateResponse>('/admin/packs/activate', request)
}

