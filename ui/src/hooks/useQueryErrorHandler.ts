/**
 * Query error handling helper
 * 
 * Integrates TanStack Query errors with Snackbar notifications.
 * Uses errorHandling utilities to normalize errors and display user-friendly messages.
 */

import { useSnackbar } from '../components/common/SnackbarProvider'
import { normalizeError, formatErrorMessage } from '../utils/errorHandling'

/**
 * Hook to get error handler for TanStack Query
 * 
 * Returns a function that can be used in query/mutation onError callbacks
 * to show snackbar notifications for errors.
 * 
 * @returns Error handler function
 * 
 * @example
 * ```ts
 * const handleError = useQueryErrorHandler()
 * 
 * useQuery({
 *   queryKey: ['key'],
 *   queryFn: fetchData,
 *   onError: handleError,
 * })
 * ```
 */
export function useQueryErrorHandler() {
  const { showError } = useSnackbar()

  return (error: unknown) => {
    const normalizedError = normalizeError(error)
    const message = formatErrorMessage(normalizedError)
    showError(message)
  }
}

