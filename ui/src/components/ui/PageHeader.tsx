/**
 * PageHeader Component (Wave 1 Enhanced)
 * 
 * A consistent page header with:
 * - Strong title typography
 * - Muted subtitle
 * - Optional right-side actions
 * - Optional last updated timestamp
 * - Responsive layout
 * 
 * Uses MUI theme tokens for automatic light/dark mode support.
 */

import { Box, Stack, Typography, IconButton, Tooltip, type SxProps, type Theme } from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import { typographyScale } from '../../theme/tokens'

export interface PageHeaderProps {
  /** Main page title */
  title: string
  /** Subtitle/description */
  subtitle?: string
  /** Right-side action buttons */
  actions?: React.ReactNode
  /** Children rendered below title */
  children?: React.ReactNode
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
  children,
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
        <Box sx={{ flexGrow: 1 }}>
          <Typography
            variant="h4"
            component="h1"
            sx={{
              ...typographyScale.pageTitle,
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
                ...typographyScale.pageSubtitle,
                color: 'text.secondary',
              }}
            >
              {subtitle}
            </Typography>
          )}
          {lastUpdatedStr && (
            <Typography
              variant="caption"
              sx={{
                ...typographyScale.caption,
                color: 'text.secondary',
                display: 'block',
                mt: 0.5,
              }}
            >
              Last updated: {lastUpdatedStr}
            </Typography>
          )}
        </Box>
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
          {onRefresh && (
            <Tooltip title="Refresh">
              <IconButton
                onClick={onRefresh}
                size="small"
                sx={{
                  color: 'text.secondary',
                  '&:hover': {
                    backgroundColor: 'action.hover',
                    color: 'text.primary',
                  },
                }}
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          )}
          {actions}
        </Box>
      </Stack>
      {children}
    </Box>
  )
}
