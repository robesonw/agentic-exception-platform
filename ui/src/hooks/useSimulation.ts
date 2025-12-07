/**
 * TanStack Query hooks for simulation endpoints
 * 
 * Provides hooks for:
 * - Getting simulation results
 * 
 * All hooks include tenantId in query keys and handle errors via snackbar.
 */

import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { useTenant } from './useTenant'
import { getSimulation } from '../api/simulation'
import type { SimulationResponse } from '../types/simulation'

/**
 * Query key factory for simulation-related queries
 */
export const simulationKeys = {
  /** All simulation queries */
  all: ['simulations'] as const,
  /** Simulation detail queries */
  details: () => [...simulationKeys.all, 'detail'] as const,
  /** Simulation detail query */
  detail: (tenantId: string | null, simulationId: string) =>
    [...simulationKeys.details(), tenantId, simulationId] as const,
}

/**
 * Hook to fetch simulation result by simulation ID
 * 
 * @param simulationId Simulation identifier
 * @returns Query result with simulation data and comparison
 */
export function useSimulation(
  simulationId: string
): UseQueryResult<SimulationResponse, Error> {
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: simulationKeys.detail(tenantId, simulationId),
    queryFn: () => getSimulation(simulationId),
    enabled: !!tenantId && !!simulationId,
    staleTime: 60_000, // 1 minute
  })
}

