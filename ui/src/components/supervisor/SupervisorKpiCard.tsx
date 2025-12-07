/**
 * Supervisor KPI Card Component
 * 
 * Reusable card component for displaying key performance indicators
 * in the Supervisor Dashboard. Provides consistent styling and layout.
 */

import { Card, CardContent, Typography, Box, Stack, useTheme } from '@mui/material'

export interface SupervisorKpiCardProps {
  /** KPI label/description */
  label: string
  /** KPI value (number or string) */
  value: number | string
  /** Optional trend text (e.g., "+5 vs last week") */
  trendLabel?: string
  /** Severity level for color accent */
  severity?: 'normal' | 'warning' | 'critical'
  /** Optional icon to display */
  icon?: React.ReactNode
  /** Additional CSS styling */
  sx?: Record<string, unknown>
}

/**
 * Supervisor KPI Card Component
 * 
 * Displays a key performance indicator with consistent styling.
 * Supports severity-based color accents and optional trend information.
 */
export default function SupervisorKpiCard({
  label,
  value,
  trendLabel,
  severity = 'normal',
  icon,
  sx,
}: SupervisorKpiCardProps) {
  const theme = useTheme()

  // Determine border color based on severity
  const getBorderColor = () => {
    switch (severity) {
      case 'warning':
        return theme.palette.warning.main
      case 'critical':
        return theme.palette.error.main
      default:
        return 'transparent'
    }
  }

  // Determine text color for trend label based on severity
  const getTrendColor = () => {
    switch (severity) {
      case 'warning':
        return theme.palette.warning.main
      case 'critical':
        return theme.palette.error.main
      default:
        return theme.palette.text.secondary
    }
  }

  // Build accessible label for screen readers
  const ariaLabel = trendLabel
    ? `${label}: ${value}${typeof value === 'number' ? ' items' : ''}. ${trendLabel}`
    : `${label}: ${value}${typeof value === 'number' ? ' items' : ''}`

  return (
    <Card
      sx={{
        height: '100%',
        borderLeft: severity !== 'normal' ? 4 : 0,
        borderLeftColor: getBorderColor(),
        ...sx,
      }}
      aria-label={ariaLabel}
      role="region"
    >
      <CardContent>
        <Stack spacing={1}>
          {/* Header: Value and Icon */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Typography variant="h4" component="div" sx={{ fontWeight: 600 }} aria-label={`Value: ${value}`}>
              {typeof value === 'number' ? value.toLocaleString() : value}
            </Typography>
            {icon && (
              <Box
                sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center' }}
                aria-hidden="true"
              >
                {icon}
              </Box>
            )}
          </Box>

          {/* Label */}
          <Typography variant="caption" color="text.secondary" component="div">
            {label}
          </Typography>

          {/* Trend Label (optional) */}
          {trendLabel && (
            <Typography
              variant="body2"
              sx={{
                color: getTrendColor(),
                fontSize: '0.75rem',
                fontWeight: severity !== 'normal' ? 600 : 400,
              }}
              aria-label={`Trend: ${trendLabel}`}
            >
              {trendLabel}
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  )
}

