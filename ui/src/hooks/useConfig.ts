/**
 * TanStack Query hooks for configuration viewing endpoints
 * 
 * Provides hooks for:
 * - Listing domain packs
 * - Getting domain pack, tenant policy, and playbook details
 * - Diffing configurations
 * - Getting configuration history
 * 
 * All hooks include tenantId in query keys and handle errors via snackbar.
 */

import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { useTenant } from './useTenant'
import {
  listDomainPacks,
  getDomainPackDetail,
  getTenantPolicyDetail,
  getPlaybookDetail,
  getConfigDiff,
  getConfigHistory,
  getGuardrailRecommendations,
  type ListDomainPacksParams,
  type ConfigDiffParams,
  type GuardrailRecommendationsParams,
} from '../api/config'
import type {
  ConfigListResponse,
  ConfigDetailResponse,
  ConfigDiffResponse,
  ConfigHistoryResponse,
  ConfigType,
  GuardrailRecommendationsResponse,
} from '../types'

/**
 * Query key factory for config-related queries
 */
export const configKeys = {
  /** All config queries */
  all: ['config'] as const,
  /** Domain packs queries */
  domainPacks: () => [...configKeys.all, 'domain-packs'] as const,
  /** Domain packs list query */
  domainPacksList: (tenantId: string | null, params?: ListDomainPacksParams) =>
    [...configKeys.domainPacks(), 'list', tenantId, params] as const,
  /** Domain pack detail query */
  domainPackDetail: (tenantId: string | null, id: string) =>
    [...configKeys.domainPacks(), 'detail', tenantId, id] as const,
  /** Tenant policies queries */
  tenantPolicies: () => [...configKeys.all, 'tenant-policies'] as const,
  /** Tenant policy detail query */
  tenantPolicyDetail: (tenantId: string | null, id: string) =>
    [...configKeys.tenantPolicies(), 'detail', tenantId, id] as const,
  /** Playbooks queries */
  playbooks: () => [...configKeys.all, 'playbooks'] as const,
  /** Playbook detail query */
  playbookDetail: (tenantId: string | null, id: string) =>
    [...configKeys.playbooks(), 'detail', tenantId, id] as const,
  /** Config diff queries */
  diff: (tenantId: string | null, params: ConfigDiffParams) =>
    [...configKeys.all, 'diff', tenantId, params] as const,
  /** Config history queries */
  history: (tenantId: string | null, type: ConfigType, id: string) =>
    [...configKeys.all, 'history', tenantId, type, id] as const,
}

/**
 * Hook to fetch list of domain packs
 * 
 * @param params Optional query parameters (tenant_id, domain)
 * @returns Query result with domain packs list
 */
export function useDomainPacks(
  params?: ListDomainPacksParams
): UseQueryResult<ConfigListResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: configKeys.domainPacksList(tenantId, params),
    queryFn: () => listDomainPacks(params),
    enabled: !!tenantId, // Can work without tenantId (admin view)
    staleTime: 120_000, // 2 minutes (configs change infrequently)
  })
}

/**
 * Hook to fetch domain pack detail
 * 
 * @param id Domain pack identifier (format: tenant_id:domain:version)
 * @returns Query result with domain pack detail
 */
export function useDomainPackDetail(
  id: string
): UseQueryResult<ConfigDetailResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: configKeys.domainPackDetail(tenantId, id),
    queryFn: () => getDomainPackDetail(id),
    enabled: !!id,
    staleTime: 300_000, // 5 minutes (config details change very infrequently)
  })
}

/**
 * Hook to fetch tenant policy detail
 * 
 * Note: There is no list endpoint for tenant policies in the backend.
 * Use this hook with a known config_id.
 * 
 * @param id Tenant policy identifier (format: tenant_id:domain)
 * @returns Query result with tenant policy detail
 */
export function useTenantPolicyDetail(
  id: string
): UseQueryResult<ConfigDetailResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: configKeys.tenantPolicyDetail(tenantId, id),
    queryFn: () => getTenantPolicyDetail(id),
    enabled: !!id,
    staleTime: 300_000, // 5 minutes
  })
}

/**
 * Hook to fetch playbook detail
 * 
 * Note: There is no list endpoint for playbooks in the backend.
 * Use this hook with a known config_id.
 * 
 * @param id Playbook identifier (format: tenant_id:domain:exception_type)
 * @returns Query result with playbook detail
 */
export function usePlaybookDetail(
  id: string
): UseQueryResult<ConfigDetailResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: configKeys.playbookDetail(tenantId, id),
    queryFn: () => getPlaybookDetail(id),
    enabled: !!id,
    staleTime: 300_000, // 5 minutes
  })
}

/**
 * Hook to fetch configuration diff
 * 
 * @param params Diff parameters (type, leftVersion, rightVersion)
 * @returns Query result with configuration diff
 */
export function useConfigDiff(
  params: ConfigDiffParams
): UseQueryResult<ConfigDiffResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: configKeys.diff(tenantId, params),
    queryFn: () => getConfigDiff(params),
    enabled: !!params.type && !!params.leftVersion && !!params.rightVersion,
    staleTime: 300_000, // 5 minutes (diffs are static)
  })
}

/**
 * Hook to fetch configuration version history
 * 
 * @param type Configuration type
 * @param id Configuration identifier
 * @returns Query result with configuration history
 */
export function useConfigHistory(
  type: ConfigType,
  id: string
): UseQueryResult<ConfigHistoryResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: configKeys.history(tenantId, type, id),
    queryFn: () => getConfigHistory(type, id),
    enabled: !!type && !!id,
    staleTime: 300_000, // 5 minutes (history changes infrequently)
  })
}

/**
 * Query key factory for recommendations
 */
export const recommendationKeys = {
  /** All recommendation queries */
  all: ['recommendations'] as const,
  /** Guardrail recommendations */
  guardrail: (tenantId: string | null, domain: string | null, guardrailId?: string) =>
    [...recommendationKeys.all, 'guardrail', tenantId, domain, guardrailId] as const,
}

/**
 * Hook to fetch guardrail recommendations
 * 
 * @param params Recommendation parameters (tenantId, domain, optional guardrailId)
 * @returns Query result with guardrail recommendations
 */
export function useGuardrailRecommendations(
  params: GuardrailRecommendationsParams
): UseQueryResult<GuardrailRecommendationsResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: recommendationKeys.guardrail(tenantId, params.domain, params.guardrailId),
    queryFn: () => getGuardrailRecommendations(params),
    enabled: !!params.tenantId && !!params.domain,
    staleTime: 300_000, // 5 minutes (recommendations change infrequently)
  })
}

