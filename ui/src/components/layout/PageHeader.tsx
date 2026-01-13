/**
 * PageHeader Component
 * 
 * Consistent page header with title, subtitle, and optional actions.
 * Uses MUI theme tokens for automatic light/dark mode support.
 * 
 * Specs:
 * - Title: bold, large (h4)
 * - Subtitle: muted, secondary text
 * - Actions: right-aligned (responsive)
 * - Fixed spacing below: 24px (mb: 3)
 */

import { Box, Stack, Typography, IconButton, Tooltip, type SxProps, type Theme } from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'

export interface PageHeaderProps {
  /** Main page title */
  title: string
  /** Subtitle/description */
  subtitle?: string
  /** Right-side action buttons */
  actions?: React.ReactNode
  /** Last updated timestamp */
  lastUpdated?: Date | string | null
  /** Refresh callback */
  onRefresh?: () => void
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function PageHeader({
  title,
  subtitle,
  actions,
  lastUpdated,
  onRefresh,
  sx,
}: PageHeaderProps) {
  const formatLastUpdated = (date: Date | string | null | undefined): string | null => {
    if (!date) return null
    const d = typeof date === 'string' ? new Date(date) : date
    if (isNaN(d.getTime())) return null
    return d.toLocaleString()
  }

  const lastUpdatedStr = formatLastUpdated(lastUpdated)

  return (
    <Box sx={{ mb: 3, ...sx }}> {/* 24px margin to first section */}
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={2}
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        justifyContent="space-between"
      >
        {/* Title + Subtitle Block */}
        <Box sx={{ flexGrow: 1 }}>
          <Typography
            variant="h4"
            component="h1"
            sx={{
              fontWeight: 700,
              fontSize: '1.75rem',
              lineHeight: 1.2,
              color: 'text.primary',
              mb: subtitle ? 0.5 : 0,
            }}
          >
            {title}
          </Typography>
          {subtitle && (
            <Typography
              variant="body1"
              sx={{
                fontSize: '0.9375rem',
                color: 'text.secondary',
                lineHeight: 1.5,
              }}
            >
              {subtitle}
            </Typography>
          )}
          {lastUpdatedStr && (
            <Typography
              variant="caption"
              sx={{
                display: 'block',
                mt: 0.5,
                color: 'text.secondary',
                fontSize: '0.75rem',
              }}
            >
              Last updated: {lastUpdatedStr}
            </Typography>
          )}
        </Box>

        {/* Actions Block */}
        <Box
          sx={{
            display: 'flex',
            gap: 1.5,
            flexWrap: 'wrap',
            width: { xs: '100%', sm: 'auto' },
            justifyContent: { xs: 'flex-start', sm: 'flex-end' },
            alignItems: 'center',
          }}
        >
          {actions}
          {onRefresh && (
            <Tooltip title="Refresh">
              <IconButton
                onClick={onRefresh}
                size="small"
                sx={{
                  color: 'text.secondary',
                  '&:hover': {
                    backgroundColor: 'action.hover',
                  },
                }}
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Stack>
    </Box>
  )
}
