import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Alert, Typography, Button, Paper } from '@mui/material'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import WarningIcon from '@mui/icons-material/Warning'

interface DeprecatedPageProps {
  oldPath: string
  newPath: string
  description?: string
}

/**
 * DeprecatedPage Component
 * 
 * Displays a deprecation notice and redirects users to the new location.
 * Can also be used as a wrapper that automatically redirects after a delay.
 */
export default function DeprecatedPage({ oldPath, newPath, description }: DeprecatedPageProps) {
  const navigate = useNavigate()

  // Auto-redirect after 5 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      navigate(newPath, { replace: true })
    }, 5000)

    return () => clearTimeout(timer)
  }, [navigate, newPath])

  const defaultDescription = description || `This page has moved to the Admin section for better organization.`

  return (
    <Box sx={{ p: 4, maxWidth: 800, mx: 'auto', mt: 4 }}>
      <Paper sx={{ p: 4 }}>
        <Alert 
          severity="info" 
          icon={<WarningIcon />}
          sx={{ mb: 3 }}
        >
          <Typography variant="h6" gutterBottom>
            Page Moved
          </Typography>
          <Typography variant="body2">
            {defaultDescription}
          </Typography>
        </Alert>

        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            <strong>Old path:</strong> {oldPath}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>New path:</strong> {newPath}
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Button
            variant="contained"
            endIcon={<ArrowForwardIcon />}
            onClick={() => navigate(newPath, { replace: true })}
          >
            Go to New Location
          </Button>
          <Typography variant="body2" color="text.secondary">
            (Auto-redirecting in 5 seconds...)
          </Typography>
        </Box>
      </Paper>
    </Box>
  )
}

