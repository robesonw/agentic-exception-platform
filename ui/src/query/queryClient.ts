/**
 * TanStack Query client configuration
 * 
 * Provides sensible defaults for the operator console:
 * - Low retry count (operator console should fail fast)
 * - Reasonable stale time to avoid overfetching
 * - No refetch on window focus (operator console is long-running)
 * - Global error handling via QueryCache and MutationCache
 */

import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query'

/**
 * Global error handler for queries
 * This will be set up in main.tsx after SnackbarProvider is available
 */
let globalQueryErrorHandler: ((error: unknown) => void) | null = null

/**
 * Set global error handler for query errors
 * Called from main.tsx after SnackbarProvider is available
 */
export function setGlobalQueryErrorHandler(handler: ((error: unknown) => void) | null): void {
  globalQueryErrorHandler = handler
}

/**
 * Create and configure QueryClient with sensible defaults
 */
export function createQueryClient(): QueryClient {
  const queryCache = new QueryCache({
    onError: (error) => {
      if (globalQueryErrorHandler) {
        globalQueryErrorHandler(error)
      }
    },
  })

  const mutationCache = new MutationCache({
    onError: (error) => {
      if (globalQueryErrorHandler) {
        globalQueryErrorHandler(error)
      }
    },
  })

  return new QueryClient({
    queryCache,
    mutationCache,
    defaultOptions: {
      queries: {
        // Retry once for transient network errors
        retry: 1,
        // Data is considered fresh for 30 seconds
        staleTime: 30_000, // 30 seconds
        // Don't refetch when window regains focus (operator console is long-running)
        refetchOnWindowFocus: false,
        // Refetch on reconnect (network recovery)
        refetchOnReconnect: true,
        // Don't refetch on mount if data is fresh
        refetchOnMount: true,
      },
      mutations: {
        // Retry mutations once
        retry: 1,
      },
    },
  })
}

/**
 * Default query client instance
 * Used in QueryClientProvider
 */
export const queryClient = createQueryClient()
