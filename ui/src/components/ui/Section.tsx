/**
 * Section Component
 * 
 * A content section with optional title, description, and consistent spacing.
 * Use to group related content within a page.
 * Uses MUI theme tokens for automatic light/dark mode support.
 */

import { Box, Typography, type SxProps, type Theme } from '@mui/material'
import { typographyScale } from '../../theme/tokens'

export interface SectionProps {
  /** Section title */
  title?: string
  /** Section description */
  description?: string
  /** Section content */
  children: React.ReactNode
  /** Right-side actions */
  actions?: React.ReactNode
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function Section({
  title,
  description,
  children,
  actions,
  sx,
}: SectionProps) {
  return (
    <Box sx={{ mb: 4, ...sx }}> {/* 32px margin between sections */}
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
                ...typographyScale.sectionTitle,
                color: 'text.primary',
              }}
            >
              {title}
            </Typography>
          )}
          {actions && (
            <Box sx={{ ml: 2, display: 'flex', gap: 1 }}>
              {actions}
            </Box>
          )}
        </Box>
      )}
      {description && (
        <Typography
          variant="body2"
          sx={{
            ...typographyScale.muted,
            color: 'text.secondary',
            mb: 2,
          }}
        >
          {description}
        </Typography>
      )}
      {children}
    </Box>
  )
}
