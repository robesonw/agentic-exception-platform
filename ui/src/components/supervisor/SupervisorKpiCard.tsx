/**
 * Supervisor KPI Card Component
 * 
 * Reusable card component for displaying key performance indicators
 * in the Supervisor Dashboard. Provides consistent styling and layout.
 * Uses MUI theme tokens for automatic light/dark mode support.
 */

import { Card, CardContent, Typography, Box, Stack, useTheme } from '@mui/material'
import { severityColors, typographyScale } from '../../theme/tokens'

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

// Muted border colors from design tokens
const severityBorderColors = {
  normal: 'transparent',
  warning: severityColors.high.border,      // Amber
  critical: severityColors.critical.border, // Red
}

const severityTextColors = {
  normal: '', // Will use theme text.secondary
  warning: severityColors.high.text,        // Amber
  critical: severityColors.critical.text,   // Red
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
  const borderColor = severityBorderColors[severity]
  const trendColor = severity === 'normal' 
    ? theme.palette.text.secondary 
    : severityTextColors[severity]

  // Build accessible label for screen readers
  const ariaLabel = trendLabel
    ? `${label}: ${value}${typeof value === 'number' ? ' items' : ''}. ${trendLabel}`
    : `${label}: ${value}${typeof value === 'number' ? ' items' : ''}`

  return (
    <Card
      sx={{
        height: '100%',
        backgroundColor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        borderLeft: severity !== 'normal' ? `4px solid ${borderColor}` : undefined,
        boxShadow: 'none',
        ...sx,
      }}
      aria-label={ariaLabel}
      role="region"
    >
      <CardContent sx={{ p: 2.5 }}>
        <Stack spacing={1}>
          {/* Header: Value and Icon */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Typography 
              component="div" 
              sx={{ ...typographyScale.kpiValue, color: 'text.primary' }}
              aria-label={`Value: ${value}`}
            >
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
          <Typography sx={{ ...typographyScale.kpiLabel, color: 'text.secondary' }} component="div">
            {label}
          </Typography>

          {/* Trend Label (optional) */}
          {trendLabel && (
            <Typography
              variant="body2"
              sx={{
                color: trendColor,
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

