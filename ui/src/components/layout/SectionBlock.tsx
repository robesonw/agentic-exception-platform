/**
 * SectionBlock Component
 * 
 * Groups related content with consistent vertical spacing.
 * Uses MUI theme tokens for automatic light/dark mode support.
 * 
 * Specs:
 * - Vertical spacing between sections: 32px (mb: 4)
 * - Optional section title (semibold, h6)
 * - Optional description (muted)
 * - Content always wrapped (never free-floating)
 */

import { Box, Typography, type SxProps, type Theme } from '@mui/material'

export interface SectionBlockProps {
  /** Section title */
  title?: string
  /** Section description */
  description?: string
  /** Section content */
  children: React.ReactNode
  /** Right-side actions */
  actions?: React.ReactNode
  /** Remove bottom margin (for last section) */
  noMargin?: boolean
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function SectionBlock({
  title,
  description,
  children,
  actions,
  noMargin = false,
  sx,
}: SectionBlockProps) {
  return (
    <Box sx={{ mb: noMargin ? 0 : 4, ...sx }}> {/* 32px margin between sections */}
      {/* Header Row */}
      {(title || actions) && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            mb: description ? 0.5 : 2,
          }}
        >
          {title && (
            <Typography
              variant="h6"
              component="h2"
              sx={{
                fontWeight: 600,
                fontSize: '1.0625rem',
                color: 'text.primary',
              }}
            >
              {title}
            </Typography>
          )}
          {actions && (
            <Box sx={{ ml: 2, display: 'flex', gap: 1, flexShrink: 0 }}>
              {actions}
            </Box>
          )}
        </Box>
      )}

      {/* Description */}
      {description && (
        <Typography
          variant="body2"
          sx={{
            color: 'text.secondary',
            fontSize: '0.875rem',
            mb: 2,
          }}
        >
          {description}
        </Typography>
      )}

      {/* Content */}
      {children}
    </Box>
  )
}
