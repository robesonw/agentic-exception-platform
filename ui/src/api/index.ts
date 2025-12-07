/**
 * API client functions
 * 
 * Central export point for all API client modules.
 * Individual modules remain the source of truth.
 * 
 * See:
 * - exceptions.ts: Exception-related endpoints
 * - supervisor.ts: Supervisor dashboard endpoints
 * - config.ts: Configuration viewing endpoints
 * - explanations.ts: Explanation endpoints
 * - simulation.ts: Simulation and rerun endpoints
 */

// Re-export all API functions from individual modules
export * from './exceptions'
export * from './supervisor'
export * from './config'
export * from './explanations'
export * from './simulation'
