/**
 * Demo API client
 * 
 * Provides access to demo mode controls and scenario execution.
 * Used by the Admin Demo Settings page.
 */

import { httpClient } from '../utils/httpClient'

// ============================================================================
// Types - Aligned with backend router_demo.py response models
// ============================================================================

export type DemoRunMode = 'burst' | 'scheduled' | 'continuous'
export type DemoRunStatus = 'pending' | 'running' | 'completed' | 'cancelled' | 'failed'
export type Industry = 'finance' | 'insurance' | 'healthcare' | 'retail' | 'saas_ops'

/**
 * Backend: DemoSettingsResponse
 */
export interface DemoSettings {
  enabled: boolean
  catalog_path?: string
  catalog_version?: string
  bootstrap_on_start: boolean
  scenarios_enabled: boolean
  scenarios_mode: string
  scenarios_active: string[]
  scenarios_tenants: string[]
  frequency_seconds: number
  duration_seconds: number
  burst_count: number
  intensity_multiplier: number
  last_run_at?: string
  bootstrap_last_at?: string
}

/**
 * Backend: DemoSettingsUpdate
 */
export interface DemoSettingsUpdate {
  enabled?: boolean
  scenarios_enabled?: boolean
  scenarios_mode?: string
  scenarios_active?: string[]
  scenarios_tenants?: string[]
  frequency_seconds?: number
  duration_seconds?: number
  burst_count?: number
  intensity_multiplier?: number
}

/**
 * Backend: DemoRunResponse
 */
export interface DemoRun {
  run_id: string
  status: DemoRunStatus
  mode: DemoRunMode
  scenario_ids: string[]
  tenant_keys: string[]
  frequency_seconds?: number
  duration_seconds?: number
  burst_count?: number
  started_at?: string
  ends_at?: string
  generated_count: number
  error?: string
}

/**
 * Backend: DemoStatusResponse
 */
export interface DemoStatus {
  enabled: boolean
  bootstrap_complete: boolean
  bootstrap_last_at?: string
  tenant_count: number
  exception_count: number
  playbook_count: number
  tool_count: number
  scenarios_available: string[]
  scenarios_active: string[]
  active_run?: DemoRun
}

export interface WeightedChoice {
  value: string
  weight: number
}

export interface ScenarioWeights {
  exception_types: WeightedChoice[]
  sources: WeightedChoice[]
  severities: WeightedChoice[]
  statuses?: WeightedChoice[]
}

export interface DemoScenario {
  scenario_id: string
  name: string
  description: string
  industry: Industry
  tags: string[]
}

export interface DemoTenant {
  tenant_key: string
  display_name: string
  industry: Industry
  tags: string[]
}

/**
 * Backend: /demo/catalog response
 */
export interface DemoCatalog {
  version: string
  tenants: DemoTenant[]
  scenarios: DemoScenario[]
  domain_packs: Array<{
    domain_name: string
    version: string
    industry: string
  }>
  error?: string
}

/**
 * Backend: DemoRunStartRequest
 */
export interface StartRunRequest {
  mode: DemoRunMode
  scenario_ids?: string[]
  tenant_keys?: string[]
  frequency_seconds?: number
  duration_seconds?: number
  burst_count?: number
  intensity_multiplier?: number
}

/**
 * Backend: DemoBootstrapResponse
 */
export interface BootstrapResponse {
  success: boolean
  message?: string
  tenants_created: number
  tenants_existing: number
  domain_packs_created: number
  playbooks_created: number
  tools_created: number
  exceptions_created: number
  errors: string[]
}

/**
 * Backend: DemoResetResponse  
 */
export interface ResetResponse {
  success: boolean
  message: string
  tenants_reset: string[]
  exceptions_deleted: number
}

/**
 * Backend: DemoRunResponse also used for stop response
 */
export type StartRunResponse = DemoRun
export type StopRunResponse = DemoRun | null

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get current demo settings
 */
export async function getDemoSettings(): Promise<DemoSettings> {
  return httpClient.get<DemoSettings>('/api/platform/settings/demo')
}

/**
 * Update demo settings
 */
export async function updateDemoSettings(settings: Partial<DemoSettings>): Promise<DemoSettings> {
  return httpClient.put<DemoSettings>('/api/platform/settings/demo', settings)
}

/**
 * Get current demo status including active run
 */
export async function getDemoStatus(): Promise<DemoStatus> {
  return httpClient.get<DemoStatus>('/api/demo/status')
}

/**
 * Get available demo catalog (scenarios and tenants)
 */
export async function getDemoCatalog(): Promise<DemoCatalog> {
  return httpClient.get<DemoCatalog>('/api/demo/catalog')
}

/**
 * Run demo bootstrap to set up demo tenants and seed data
 */
export async function runBootstrap(): Promise<BootstrapResponse> {
  return httpClient.post<BootstrapResponse>('/api/demo/bootstrap')
}

/**
 * Start a demo run
 */
export async function startDemoRun(request: StartRunRequest): Promise<StartRunResponse> {
  return httpClient.post<StartRunResponse>('/api/demo/run/start', request)
}

/**
 * Stop the current demo run
 */
export async function stopDemoRun(): Promise<StopRunResponse> {
  return httpClient.post<StopRunResponse>('/api/demo/run/stop')
}

/**
 * Reset demo data (delete demo exceptions and optionally reset tenants)
 */
export async function resetDemoData(deleteTenants: boolean = false): Promise<ResetResponse> {
  return httpClient.post<ResetResponse>('/api/demo/reset', { delete_tenants: deleteTenants })
}
