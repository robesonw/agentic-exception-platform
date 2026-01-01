/**
 * Section Component
 * 
 * Groups related content with consistent vertical spacing.
 * Uses MUI theme tokens for automatic light/dark mode support.
 * Provides optional section header with title, description, and actions.
 * 
 * Features:
 * - Consistent vertical rhythm: 32px margin between sections
 * - Optional section header (title + actions)
 * - Optional description text
 * - Semantic h2 element for accessibility
 * 
 * Usage:
 *   <Section 
 *     title="Recent Exceptions"
 *     description="Last 24 hours of activity"
 *     actions={<Button size="small">View All</Button>}
 *   >
 *     <DataTable ... />
 *   </Section>
 * 
 * Spacing:
 * - Section to section: 32px (mb: 4)
 * - Title to content: 16px (mb: 2)
 * - Description adds 8px above content
 */

import { Box, Typography, type SxProps, type Theme } from '@mui/material'
import { typography } from '../../theme/globalDesignSystem'

export interface SectionProps {
  /** Section title */
  title?: string
  /** Section description */
  description?: string
  /** Right-side actions */
  actions?: React.ReactNode
  /** Section content */
  children: React.ReactNode
  /** Remove bottom margin (for last section on page) */
  noMargin?: boolean
  /** Reduce spacing for compact layouts */
  compact?: boolean
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function Section({
  title,
  description,
  actions,
  children,
  noMargin = false,
  compact = false,
  sx,
}: SectionProps) {
  const hasHeader = title || actions
  const marginBottom = noMargin ? 0 : compact ? 3 : 4 // 24px compact, 32px normal

  return (
    <Box sx={{ mb: marginBottom, ...sx }}>
      {/* Header Row: Title (left) + Actions (right) */}
      {hasHeader && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 2,
            mb: description ? 0.5 : 2, // Tighter if description follows
          }}
        >
          {title && (
            <Typography
              variant="h6"
              component="h2"
              sx={{
                ...typography.sectionTitle,
                color: 'text.primary',
              }}
            >
              {title}
            </Typography>
          )}
          {actions && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                flexShrink: 0,
              }}
            >
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
            ...typography.sectionSubtitle,
            color: 'text.secondary',
            mb: 2, // 16px to content
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
