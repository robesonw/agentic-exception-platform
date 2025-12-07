/**
 * Simulation types
 * 
 * Mirrors backend models from:
 * - src/api/routes/router_simulation.py (RerunRequest, RerunResponse, SimulationResponse)
 */

/**
 * Rerun request payload
 * Mirrors RerunRequest from router_simulation.py
 */
export interface RerunRequest {
  /** Tenant identifier */
  tenant_id: string
  /** Optional overrides: severity, policies, playbook */
  overrides?: Record<string, unknown>
  /** Whether to run in simulation mode (default: true) */
  simulation?: boolean
}

/**
 * Rerun response
 * Mirrors RerunResponse from router_simulation.py
 */
export interface RerunResponse {
  /** Simulation identifier */
  simulation_id: string
  /** Original exception ID */
  original_exception_id: string
  /** Simulated exception record */
  simulated_exception: Record<string, unknown>
  /** Pipeline processing result */
  pipeline_result: Record<string, unknown>
  /** Overrides that were applied */
  overrides_applied: Record<string, unknown>
  /** Simulation timestamp */
  timestamp: string
  /** Comparison with original run (if available) */
  comparison?: Record<string, unknown> | null
}

/**
 * Simulation response
 * Mirrors SimulationResponse from router_simulation.py
 */
export interface SimulationResponse {
  /** Simulation identifier */
  simulation_id: string
  /** Original exception ID */
  original_exception_id: string
  /** Simulated exception record */
  simulated_exception: Record<string, unknown>
  /** Pipeline processing result */
  pipeline_result: Record<string, unknown>
  /** Overrides that were applied */
  overrides_applied: Record<string, unknown>
  /** Simulation timestamp */
  timestamp: string
  /** Comparison with original run */
  comparison?: Record<string, unknown> | null
}

