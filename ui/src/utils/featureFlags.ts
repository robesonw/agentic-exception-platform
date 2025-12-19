/**
 * Feature flag utilities
 * Reads environment variables to control feature visibility
 */

/**
 * Check if Ops features are enabled
 */
export function isOpsEnabled(): boolean {
  return import.meta.env.VITE_OPS_ENABLED === 'true' || import.meta.env.VITE_ENABLE_OPS_PAGE === 'true'
}

/**
 * Check if Admin features are enabled
 */
export function isAdminEnabled(): boolean {
  return import.meta.env.VITE_ADMIN_ENABLED === 'true'
}

/**
 * Check if user has required role (if RBAC exists)
 * For MVP, this is a placeholder - can be enhanced with actual RBAC
 */
export function hasRole(requiredRole: 'viewer' | 'operator' | 'admin'): boolean {
  // TODO: Integrate with actual RBAC system when available
  // For now, return true if feature flags are enabled
  if (requiredRole === 'admin') {
    return isAdminEnabled()
  }
  if (requiredRole === 'operator') {
    return isOpsEnabled() || isAdminEnabled()
  }
  return true // viewer is default
}

