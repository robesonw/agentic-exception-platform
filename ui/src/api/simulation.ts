/**
 * API client for simulation and rerun endpoints
 * 
 * Mirrors backend routes from:
 * - src/api/routes/router_simulation.py
 * 
 * All functions automatically include tenantId via httpClient interceptors.
 */

import { httpClient } from '../utils/httpClient'
import type { RerunRequest, RerunResponse, SimulationResponse } from '../types/simulation'

/**
 * Re-run an exception with optional overrides in simulation mode
 * POST /ui/exceptions/{exception_id}/rerun
 * 
 * @param exceptionId Exception identifier to re-run
 * @param request Rerun request with tenant_id, overrides, and simulation flag
 * @returns Rerun response with simulation result and comparison
 */
export async function rerunException(
  exceptionId: string,
  request: RerunRequest
): Promise<RerunResponse> {
  return httpClient.post<RerunResponse>(
    `/ui/exceptions/${exceptionId}/rerun`,
    request
  )
}

/**
 * Get simulation result by simulation ID
 * GET /ui/simulations/{simulation_id}
 * 
 * @param simulationId Simulation identifier
 * @returns Simulation response with result and comparison
 */
export async function getSimulation(
  simulationId: string
): Promise<SimulationResponse> {
  return httpClient.get<SimulationResponse>(`/ui/simulations/${simulationId}`)
}

