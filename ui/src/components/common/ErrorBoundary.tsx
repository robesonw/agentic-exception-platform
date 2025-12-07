import React, { Component, ReactNode } from 'react'
import { Box, Typography, Button, Paper } from '@mui/material'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
    }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      error,
    }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error to console for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
    })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '50vh',
            p: 3,
          }}
        >
          <Paper sx={{ p: 4, maxWidth: 500, textAlign: 'center' }}>
            <Typography variant="h5" component="h1" gutterBottom color="error">
              Something went wrong
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
              An unexpected error occurred. Please refresh the page or try again.
            </Typography>
            {import.meta.env.MODE === 'development' && this.state.error && (
              <Typography
                variant="body2"
                component="pre"
                sx={{
                  p: 2,
                  backgroundColor: 'error.light',
                  color: 'error.contrastText',
                  borderRadius: 1,
                  mb: 2,
                  textAlign: 'left',
                  overflow: 'auto',
                  fontSize: '0.75rem',
                }}
              >
                {this.state.error.toString()}
                {this.state.error.stack && `\n\n${this.state.error.stack}`}
              </Typography>
            )}
            <Button variant="contained" onClick={this.handleReset}>
              Try Again
            </Button>
            <Button
              variant="outlined"
              onClick={() => window.location.reload()}
              sx={{ ml: 2 }}
            >
              Refresh Page
            </Button>
          </Paper>
        </Box>
      )
    }

    return this.props.children
  }
}

