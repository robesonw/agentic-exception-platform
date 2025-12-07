import { Button, ButtonProps, CircularProgress, Box } from '@mui/material'

export interface LoadingButtonProps extends ButtonProps {
  /**
   * Whether the button is in a loading state
   * When true, button is disabled and shows a spinner
   */
  loading?: boolean
  /**
   * Position of the loading spinner relative to the button text
   * @default 'start'
   */
  loadingPosition?: 'start' | 'end' | 'center'
}

/**
 * LoadingButton component wraps MUI Button with loading state support
 * Shows a CircularProgress spinner when loading is true
 */
export default function LoadingButton({
  loading = false,
  loadingPosition = 'start',
  children,
  disabled,
  ...buttonProps
}: LoadingButtonProps) {
  const renderContent = () => {
    if (loading && loadingPosition === 'center') {
      // Center position: show only spinner, no text
      return <CircularProgress size={16} color="inherit" />
    }

    if (loading && loadingPosition === 'start') {
      // Start position: spinner before text
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CircularProgress size={16} color="inherit" />
          {children}
        </Box>
      )
    }

    if (loading && loadingPosition === 'end') {
      // End position: spinner after text
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {children}
          <CircularProgress size={16} color="inherit" />
        </Box>
      )
    }

    // No loading: render children normally
    return children
  }

  return (
    <Button {...buttonProps} disabled={disabled || loading}>
      {renderContent()}
    </Button>
  )
}

