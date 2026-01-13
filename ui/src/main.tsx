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
import { createAppTheme } from './theme/theme.ts'
import { ThemeModeProvider, useThemeMode } from './theme/ThemeModeProvider.tsx'

// Global Design System CSS (must be imported once at app bootstrap)
import './theme/globalStyles.css'

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

/**
 * Inner component that consumes theme mode and provides MUI theme
 */
function ThemedApp() {
  const { mode } = useThemeMode()
  const theme = createAppTheme(mode)

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <TenantProvider>
          <AppWithProviders />
        </TenantProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeModeProvider>
        <ThemedApp />
      </ThemeModeProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
