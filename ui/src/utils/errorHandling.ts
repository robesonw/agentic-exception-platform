import { AxiosError } from 'axios'

/**
 * Standardized API Error interface
 */
export interface ApiError {
  message: string
  status?: number
  details?: unknown
}

/**
 * Global error handler function type
 */
type GlobalErrorHandler = (error: ApiError) => void

let globalErrorHandler: GlobalErrorHandler | null = null

/**
 * Set global error handler for unhandled API errors
 * Called from SnackbarProvider or App root
 */
export function setGlobalErrorHandler(handler: GlobalErrorHandler | null): void {
  globalErrorHandler = handler
}

/**
 * Get current global error handler
 */
export function getGlobalErrorHandler(): GlobalErrorHandler | null {
  return globalErrorHandler
}

/**
 * Normalize any error to ApiError format
 */
export function normalizeError(err: unknown): ApiError {
  // Handle axios errors
  if (err && typeof err === 'object' && 'isAxiosError' in err) {
    const axiosError = err as AxiosError
    if (axiosError.response) {
      // Server responded with error status
      const status = axiosError.response.status
      const data = axiosError.response.data as { detail?: string; message?: string } | undefined
      const message =
        data?.detail || data?.message || axiosError.message || `Request failed (${status})`

      return {
        message,
        status,
        details: axiosError.response.data,
      }
    } else if (axiosError.request) {
      // Request made but no response received
      return {
        message: 'Network error: No response from server',
        details: axiosError.request,
      }
    } else {
      // Error setting up request
      return {
        message: `Request error: ${axiosError.message}`,
        details: axiosError,
      }
    }
  }

  // Handle ApiError instances (from httpClient)
  if (err && typeof err === 'object' && 'message' in err && 'status' in err) {
    return err as ApiError
  }

  // Handle generic Error instances
  if (err instanceof Error) {
    return {
      message: err.message || 'An error occurred',
      details: err,
    }
  }

  // Handle unknown values
  if (typeof err === 'string') {
    return {
      message: err,
    }
  }

  return {
    message: 'An unexpected error occurred',
    details: err,
  }
}

/**
 * Format error message for user display
 */
export function formatErrorMessage(error: ApiError | unknown): string {
  const apiError = error instanceof Error && 'status' in error ? (error as ApiError) : normalizeError(error)

  if (apiError.status) {
    return `Request failed (${apiError.status}): ${apiError.message}`
  }

  return apiError.message || 'An unexpected error occurred'
}

/**
 * Handle error with global handler if available
 */
export function handleError(error: unknown): void {
  const normalized = normalizeError(error)
  if (globalErrorHandler) {
    globalErrorHandler(normalized)
  }
}

