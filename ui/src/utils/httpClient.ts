import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'
import { normalizeError, handleError, type ApiError } from './errorHandling.ts'

// Re-export ApiError type from errorHandling for convenience
export type { ApiError } from './errorHandling.ts'

/**
 * Module-level tenant store for axios interceptors
 * This allows interceptors to access tenantId without React context
 */
let currentTenantId: string | null = null

/**
 * Module-level API key store for axios interceptors
 * This allows interceptors to access API key without React context
 */
let currentApiKey: string | null = null

// Initialize API key from localStorage synchronously on module load
// This ensures the API key is available before any requests are made
if (typeof window !== 'undefined') {
  try {
    const storedApiKey = localStorage.getItem('apiKey')
    if (storedApiKey) {
      currentApiKey = storedApiKey
      if (import.meta.env.DEV) {
        console.log('[httpClient] Initialized API key from localStorage on module load:', storedApiKey.substring(0, 15) + '...')
      }
    } else {
      if (import.meta.env.DEV) {
        console.warn('[httpClient] No API key found in localStorage on module load')
      }
    }
  } catch (e) {
    // localStorage might not be available (e.g., in SSR)
    console.warn('Failed to read API key from localStorage:', e)
  }
}

/**
 * Set the current tenant ID for HTTP client
 * Called by TenantProvider when tenantId changes
 */
export function setTenantIdForHttpClient(tenantId: string | null): void {
  currentTenantId = tenantId
}

/**
 * Get the current tenant ID for HTTP client
 */
export function getTenantIdForHttpClient(): string | null {
  return currentTenantId
}

/**
 * Set the current API key for HTTP client
 * Called by TenantProvider when API key changes
 */
export function setApiKeyForHttpClient(apiKey: string | null): void {
  currentApiKey = apiKey
  // Also update localStorage to keep them in sync
  if (typeof window !== 'undefined') {
    try {
      if (apiKey) {
        localStorage.setItem('apiKey', apiKey)
        if (import.meta.env.DEV) {
          console.log('[httpClient] API key set:', apiKey.substring(0, 15) + '...')
        }
      } else {
        localStorage.removeItem('apiKey')
        if (import.meta.env.DEV) {
          console.log('[httpClient] API key cleared')
        }
      }
    } catch (e) {
      console.warn('Failed to update API key in localStorage:', e)
    }
  }
}

/**
 * Get the current API key for HTTP client
 */
export function getApiKeyForHttpClient(): string | null {
  return currentApiKey
}

/**
 * Get base URL from environment variable
 */
function getBaseURL(): string {
  const baseURL = import.meta.env.VITE_API_BASE_URL
  if (!baseURL) {
    console.warn('VITE_API_BASE_URL is not set. Defaulting to http://localhost:8000')
    return 'http://localhost:8000'
  }
  return baseURL
}

/**
 * Create configured axios instance
 */
const axiosInstance: AxiosInstance = axios.create({
  baseURL: getBaseURL(),
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Request interceptor: Inject tenantId and API key into requests
 */
axiosInstance.interceptors.request.use(
  (config) => {
    // Inject API key as header (required for authentication)
    // Backend middleware expects X-API-KEY header for authentication
    // Check multiple sources in order of priority:
    // 1. currentApiKey (module-level, set by setApiKeyForHttpClient)
    // 2. localStorage (fallback, in case React state hasn't updated yet)
    const apiKeyFromStorage = typeof window !== 'undefined' ? localStorage.getItem('apiKey') : null
    const apiKeyToUse = currentApiKey || apiKeyFromStorage
    
    if (apiKeyToUse && config.headers) {
      // Set header - Axios handles header normalization
      config.headers['X-API-KEY'] = apiKeyToUse
      // Debug logging (always log in dev to help diagnose issues)
      if (import.meta.env.DEV) {
        console.log('[httpClient] ✅ Adding X-API-KEY header to', config.url || config.baseURL, ':', apiKeyToUse.substring(0, 15) + '...')
        console.log('[httpClient] Header source:', currentApiKey ? 'currentApiKey' : 'localStorage')
        console.log('[httpClient] Full header value:', apiKeyToUse)
      }
    } else {
      // Always log error when API key is missing (even in production, this is critical)
      console.error('[httpClient] ❌ No API key found! Request will fail with 401.')
      console.error('[httpClient] Debug info:', { 
        currentApiKey: currentApiKey ? currentApiKey.substring(0, 10) + '...' : null, 
        localStorage: apiKeyFromStorage ? apiKeyFromStorage.substring(0, 10) + '...' : null,
        url: config.url || config.baseURL,
        method: config.method,
        allLocalStorageKeys: typeof window !== 'undefined' ? Object.keys(localStorage) : []
      })
    }

    // Inject tenantId as query parameter if available
    // Backend UI endpoints expect tenant_id as query param
    if (currentTenantId) {
      // Ensure config.params exists before spreading
      config.params = {
        ...(config.params || {}),
        tenant_id: currentTenantId,
      }
    }

    // Also add tenantId as header (some endpoints might use this)
    if (currentTenantId && config.headers) {
      config.headers['X-Tenant-Id'] = currentTenantId
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

/**
 * Response interceptor: Normalize errors and call global handler
 */
axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  (error: AxiosError) => {
    // Normalize error using errorHandling utility
    const normalizedError = normalizeError(error)
    
    // Call global error handler if available (will show snackbar)
    handleError(normalizedError)
    
    // Reject with error that components can catch
    // Attach ApiError properties to Error object
    const errorObj = new Error(normalizedError.message) as Error & Partial<ApiError>
    errorObj.status = normalizedError.status
    errorObj.details = normalizedError.details
    throw errorObj
  }
)

/**
 * Format error message for user display
 * Re-exported from errorHandling for convenience
 */
export { formatErrorMessage } from './errorHandling.ts'

/**
 * HTTP Client API
 */
export const httpClient = {
  /**
   * GET request
   */
  async get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await axiosInstance.get<T>(url, config)
    return response.data
  },

  /**
   * POST request
   */
  async post<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await axiosInstance.post<T>(url, data, config)
    return response.data
  },

  /**
   * PUT request
   */
  async put<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await axiosInstance.put<T>(url, data, config)
    return response.data
  },

  /**
   * DELETE request
   */
  async delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await axiosInstance.delete<T>(url, config)
    return response.data
  },

  /**
   * PATCH request
   */
  async patch<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await axiosInstance.patch<T>(url, data, config)
    return response.data
  },
}

// Export axios instance for advanced use cases
export { axiosInstance }
