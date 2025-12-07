import React, { createContext, useContext, useState, ReactNode } from 'react'
import { Snackbar, Alert, AlertColor } from '@mui/material'

interface SnackbarContextValue {
  showError: (message: string) => void
  showSuccess: (message: string) => void
  showWarning: (message: string) => void
  showInfo: (message: string) => void
}

const SnackbarContext = createContext<SnackbarContextValue | undefined>(undefined)

interface SnackbarState {
  open: boolean
  message: string
  severity: AlertColor
}

interface SnackbarProviderProps {
  children: ReactNode
}

export function SnackbarProvider({ children }: SnackbarProviderProps) {
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: '',
    severity: 'info',
  })

  const showSnackbar = (message: string, severity: AlertColor) => {
    setSnackbar({
      open: true,
      message,
      severity,
    })
  }

  const showError = (message: string) => {
    showSnackbar(message, 'error')
  }

  const showSuccess = (message: string) => {
    showSnackbar(message, 'success')
  }

  const showWarning = (message: string) => {
    showSnackbar(message, 'warning')
  }

  const showInfo = (message: string) => {
    showSnackbar(message, 'info')
  }

  const handleClose = (_event?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') {
      return
    }
    setSnackbar((prev) => ({ ...prev, open: false }))
  }

  const value: SnackbarContextValue = {
    showError,
    showSuccess,
    showWarning,
    showInfo,
  }

  return (
    <SnackbarContext.Provider value={value}>
      {children}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleClose} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </SnackbarContext.Provider>
  )
}

/**
 * Hook to access snackbar context
 * @returns SnackbarContextValue with showError, showSuccess, showWarning, showInfo
 * @throws Error if used outside SnackbarProvider
 */
export function useSnackbar(): SnackbarContextValue {
  const context = useContext(SnackbarContext)
  if (context === undefined) {
    throw new Error('useSnackbar must be used within a SnackbarProvider')
  }
  return context
}

