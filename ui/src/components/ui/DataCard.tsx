/**
 * DataCard Component
 * 
 * Enterprise-grade card for tables and data-heavy content.
 * Uses MUI theme tokens for automatic light/dark mode support.
 * 
 * Structure:
 * - Header: title + subtitle + actions
 * - Filter bar: inline filters with clear separation
 * - Content: table/list (no internal padding)
 */

import { Box, Typography, type SxProps, type Theme } from '@mui/material'
import { radii, shadows } from '../../theme/tokens'

export interface DataCardProps {
  /** Card content (table/list) */
  children: React.ReactNode
  /** Card title */
  title?: string
  /** Subtitle or record count */
  subtitle?: string
  /** Header actions (buttons, etc.) */
  actions?: React.ReactNode
  /** Filter bar content */
  filterContent?: React.ReactNode
  /** Loading state */
  loading?: boolean
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function DataCard({
  children,
  title,
  subtitle,
  actions,
  filterContent,
  loading,
  sx,
}: DataCardProps) {
  return (
    <Box
      sx={{
        backgroundColor: 'background.paper',
        border: 1,
        borderColor: 'divider',
        borderRadius: `${radii.lg}px`,
        boxShadow: shadows.card,
        overflow: 'hidden',
        opacity: loading ? 0.7 : 1,
        transition: 'opacity 0.2s ease',
        ...sx,
      }}
    >
      {/* Header */}
      {(title || actions) && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2.5,   // 20px
            py: 2,     // 16px
            borderBottom: filterContent ? 'none' : 1,
            borderColor: 'divider',
          }}
        >
          <Box>
            {title && (
              <Typography
                component="h3"
                sx={{
                  fontSize: '0.9375rem',  // 15px
                  fontWeight: 600,
                  color: 'text.primary',
                  lineHeight: 1.4,
                }}
              >
                {title}
              </Typography>
            )}
            {subtitle && (
              <Typography
                component="span"
                sx={{
                  display: 'block',
                  fontSize: '0.75rem',    // 12px
                  color: 'text.secondary',
                  lineHeight: 1.4,
                  mt: 0.25,
                }}
              >
                {subtitle}
              </Typography>
            )}
          </Box>
          {actions && (
            <Box sx={{ ml: 2, display: 'flex', gap: 1, flexShrink: 0 }}>
              {actions}
            </Box>
          )}
        </Box>
      )}

      {/* Filter bar - inline, consistent height, clear separation */}
      {filterContent && (
        <Box
          sx={{
            px: 2.5,         // 20px horizontal
            py: 1.5,         // 12px vertical
            borderBottom: 1,
            borderColor: 'divider',
            backgroundColor: 'action.hover',
          }}
        >
          {filterContent}
        </Box>
      )}

      {/* Content - no padding, table handles its own */}
      <Box>
        {children}
      </Box>
    </Box>
  )
}
