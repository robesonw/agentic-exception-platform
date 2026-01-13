/**
 * StatCard Component
 * 
 * Enterprise-grade KPI/metric card for displaying key statistics.
 * Uses MUI theme tokens for automatic light/dark mode support.
 * 
 * Design principles:
 * - Equal height in grids
 * - Consistent 20px internal padding
 * - Clean visual hierarchy: Label → Value → Subtext
 * - Minimal visual noise
 */

import { Box, Typography, useTheme, type SxProps, type Theme } from '@mui/material'
import { radii, shadows } from '../../theme/tokens'

export interface StatCardProps {
  /** Metric label (small, uppercase) */
  label: string
  /** Metric value (large, bold) */
  value: string | number
  /** Optional subtitle/subtext (muted) */
  subtitle?: string
  /** Color variant for value */
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'error'
  /** Optional icon (use sparingly) */
  icon?: React.ReactNode
  /** Click handler */
  onClick?: () => void
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function StatCard({
  label,
  value,
  subtitle,
  variant = 'default',
  icon,
  onClick,
  sx,
}: StatCardProps) {
  const theme = useTheme()
  const isInteractive = Boolean(onClick)

  // Theme-aware variant colors
  const variantColors = {
    default: 'text.primary',
    primary: 'primary.main',
    success: 'success.main',
    warning: 'warning.main',
    error: 'error.main',
  }
  const valueColor = variantColors[variant]

  return (
    <Box
      onClick={onClick}
      sx={{
        backgroundColor: 'background.paper',
        border: 1,
        borderColor: 'divider',
        borderRadius: `${radii.lg}px`,
        boxShadow: shadows.card,
        p: 2.5,  // 20px consistent padding
        minHeight: 120,
        height: '100%',  // Equal height in grid
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        transition: 'box-shadow 0.15s ease, border-color 0.15s ease',
        cursor: isInteractive ? 'pointer' : 'default',
        ...(isInteractive && {
          '&:hover': {
            boxShadow: shadows.cardHover,
            borderColor: theme.palette.mode === 'dark' 
              ? 'rgba(148, 163, 184, 0.3)' 
              : 'rgba(148, 163, 184, 0.6)',
          },
        }),
        ...sx,
      }}
    >
      {/* Top section: Label + Icon */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 1,
        }}
      >
        <Typography
          component="span"
          sx={{
            fontSize: '0.6875rem',    // 11px
            fontWeight: 600,
            lineHeight: 1.4,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            color: 'text.secondary',
          }}
        >
          {label}
        </Typography>
        {icon && (
          <Box 
            sx={{ 
              color: 'text.secondary', 
              opacity: 0.6,
              '& svg': { fontSize: 18 },
              flexShrink: 0,
            }}
          >
            {icon}
          </Box>
        )}
      </Box>

      {/* Bottom section: Value + Subtitle */}
      <Box sx={{ mt: 'auto', pt: 1 }}>
        <Typography
          component="div"
          sx={{
            fontSize: '1.75rem',      // 28px - readable but not overwhelming
            fontWeight: 700,
            lineHeight: 1.1,
            letterSpacing: '-0.02em',
            color: valueColor,
          }}
        >
          {value}
        </Typography>
        {subtitle && (
          <Typography
            component="span"
            sx={{
              display: 'block',
              fontSize: '0.75rem',    // 12px
              fontWeight: 400,
              lineHeight: 1.4,
              color: 'text.secondary',
              mt: 0.5,
            }}
          >
            {subtitle}
          </Typography>
        )}
      </Box>
    </Box>
  )
}
