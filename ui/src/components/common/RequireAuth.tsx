import { ReactNode, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useTenant } from '../../hooks/useTenant'
import { getApiKeyForHttpClient } from '../../utils/httpClient'

interface RequireAuthProps {
  children: ReactNode
}

/**
 * RequireAuth component that ensures user has a valid API key before rendering children.
 * 
 * Checks both:
 * 1. React state (apiKey from TenantContext)
 * 2. Module-level variable (from httpClient)
 * 3. localStorage fallback
 * 
 * If no API key is found, redirects to /login with the current location as redirect target.
 */
export default function RequireAuth({ children }: RequireAuthProps) {
  const location = useLocation()
  const { apiKey } = useTenant()
  const [isChecking, setIsChecking] = useState(true)
  const [hasAuth, setHasAuth] = useState(false)

  useEffect(() => {
    // Check all possible sources for API key
    const apiKeyFromHttpClient = getApiKeyForHttpClient()
    const apiKeyFromStorage = typeof window !== 'undefined' ? localStorage.getItem('apiKey') : null
    
    const hasValidApiKey = !!(apiKey || apiKeyFromHttpClient || apiKeyFromStorage)
    
    setHasAuth(hasValidApiKey)
    setIsChecking(false)
  }, [apiKey])

  // Show nothing while checking (prevents flash of login page)
  if (isChecking) {
    return null
  }

  // Redirect to login if no auth
  if (!hasAuth) {
    // Preserve the attempted URL for redirect after login
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
