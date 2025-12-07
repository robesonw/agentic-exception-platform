import React, { useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider, CssBaseline } from '@mui/material'
import { QueryClientProvider } from '@tanstack/react-query'
import { TenantProvider } from './hooks/useTenant.tsx'
import { SnackbarProvider, useSnackbar } from './components/common/SnackbarProvider.tsx'
import ErrorBoundary from './components/common/ErrorBoundary.tsx'
import { setGlobalErrorHandler, normalizeError, formatErrorMessage } from './utils/errorHandling.ts'
import { queryClient, setGlobalQueryErrorHandler } from './query/queryClient.ts'
import App from './App.tsx'
import { defaultTheme } from './theme/theme.ts'

/**
 * Component that sets up global error handlers with snackbar
 */
function ErrorHandlerSetup({ children }: { children: React.ReactNode }) {
  const { showError } = useSnackbar()

  useEffect(() => {
    // Set global error handler for httpClient errors
    setGlobalErrorHandler((error) => {
      const message = formatErrorMessage(error)
      showError(message)
    })

    // Set global error handler for TanStack Query errors
    setGlobalQueryErrorHandler((error: unknown) => {
      const normalizedError = normalizeError(error)
      const message = formatErrorMessage(normalizedError)
      showError(message)
    })

    // Cleanup on unmount
    return () => {
      setGlobalErrorHandler(null)
      setGlobalQueryErrorHandler(null)
    }
  }, [showError])

  return <>{children}</>
}

function AppWithProviders() {
  return (
    <SnackbarProvider>
      <ErrorHandlerSetup>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </ErrorHandlerSetup>
    </SnackbarProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider theme={defaultTheme}>
        <CssBaseline />
        <QueryClientProvider client={queryClient}>
          <TenantProvider>
            <AppWithProviders />
          </TenantProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
