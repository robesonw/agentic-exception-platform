import { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { isOpsEnabled, isAdminEnabled } from '../../utils/featureFlags'
import NotAuthorizedPage from './NotAuthorizedPage'

interface ProtectedRouteProps {
  children: ReactNode
  requireOps?: boolean
  requireAdmin?: boolean
}

/**
 * ProtectedRoute component that checks feature flags and shows NotAuthorizedPage if access is denied
 */
export default function ProtectedRoute({
  children,
  requireOps = false,
  requireAdmin = false,
}: ProtectedRouteProps) {
  const location = useLocation()

  // Check if Ops access is required and enabled
  if (requireOps && !isOpsEnabled()) {
    return <NotAuthorizedPage />
  }

  // Check if Admin access is required and enabled
  if (requireAdmin && !isAdminEnabled()) {
    return <NotAuthorizedPage />
  }

  // TODO: Add RBAC checks here when RBAC is implemented
  // For now, feature flags are sufficient

  return <>{children}</>
}

