import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { setTenantIdForHttpClient, setApiKeyForHttpClient } from '../utils/httpClient.ts'

interface TenantContextType {
  tenantId: string | null
  domain: string | null
  apiKey: string | null
  setTenantId: (id: string | null) => void
  setDomain: (domain: string | null) => void
  setApiKey: (key: string | null) => void
}

const TenantContext = createContext<TenantContextType | undefined>(undefined)

const STORAGE_KEY_TENANT_ID = 'tenantId'
const STORAGE_KEY_TENANT_DOMAIN = 'tenantDomain'
const STORAGE_KEY_API_KEY = 'apiKey'

interface TenantProviderProps {
  children: ReactNode
}

export function TenantProvider({ children }: TenantProviderProps) {
  // Initialize state from localStorage
  const [tenantId, setTenantIdState] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(STORAGE_KEY_TENANT_ID) || null
    }
    return null
  })

  const [domain, setDomainState] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(STORAGE_KEY_TENANT_DOMAIN) || null
    }
    return null
  })

  const [apiKey, setApiKeyState] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(STORAGE_KEY_API_KEY) || null
    }
    return null
  })

  // Update localStorage when tenantId changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      if (tenantId) {
        localStorage.setItem(STORAGE_KEY_TENANT_ID, tenantId)
      } else {
        localStorage.removeItem(STORAGE_KEY_TENANT_ID)
      }
    }
  }, [tenantId])

  // Update localStorage when domain changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      if (domain) {
        localStorage.setItem(STORAGE_KEY_TENANT_DOMAIN, domain)
      } else {
        localStorage.removeItem(STORAGE_KEY_TENANT_DOMAIN)
      }
    }
  }, [domain])

  // Update localStorage when API key changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      if (apiKey) {
        localStorage.setItem(STORAGE_KEY_API_KEY, apiKey)
      } else {
        localStorage.removeItem(STORAGE_KEY_API_KEY)
      }
    }
  }, [apiKey])

  // Update HTTP client when tenantId changes
  useEffect(() => {
    setTenantIdForHttpClient(tenantId)
  }, [tenantId])

  // Update HTTP client when API key changes
  useEffect(() => {
    setApiKeyForHttpClient(apiKey)
  }, [apiKey])

  const setTenantId = (id: string | null) => {
    setTenantIdState(id)
  }

  const setDomain = (domainValue: string | null) => {
    setDomainState(domainValue)
  }

  const setApiKey = (key: string | null) => {
    setApiKeyState(key)
  }

  const value: TenantContextType = {
    tenantId,
    domain,
    apiKey,
    setTenantId,
    setDomain,
    setApiKey,
  }

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
}

/**
 * Hook to access tenant context
 * @returns TenantContextType with tenantId, domain, and setters
 * @throws Error if used outside TenantProvider
 */
export function useTenant(): TenantContextType {
  const context = useContext(TenantContext)
  if (context === undefined) {
    throw new Error('useTenant must be used within a TenantProvider')
  }
  return context
}
