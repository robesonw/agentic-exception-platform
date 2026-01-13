/**
 * EmptyState Component (Wave 1 Enhanced)
 * 
 * A clean placeholder for "no data" states.
 * Uses MUI theme tokens for automatic light/dark mode support.
 * Features:
 * - Centered layout
 * - Icon, title, description
 * - Optional action button
 */

import { Box, Typography, type SxProps, type Theme } from '@mui/material'
import InboxIcon from '@mui/icons-material/Inbox'
import { typography as typographyTokens } from '../../theme/tokens'

export interface EmptyStateProps {
  /** Main title */
  title?: string
  /** Description text */
  description?: string
  /** Custom icon (defaults to Inbox icon) */
  icon?: React.ReactNode
  /** Action element (button, link, etc.) */
  action?: React.ReactNode
  /** Compact mode (less padding) */
  compact?: boolean
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function EmptyState({
  title = 'No data available',
  description,
  icon,
  action,
  compact = false,
  sx,
}: EmptyStateProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        py: compact ? 4 : 8,
        px: 3,
        textAlign: 'center',
        ...sx,
      }}
      role="status"
      aria-live="polite"
    >
      {/* Icon */}
      <Box
        sx={{
          mb: 2,
          color: 'text.disabled',
          '& svg': {
            fontSize: compact ? 40 : 56,
          },
        }}
      >
        {icon || <InboxIcon />}
      </Box>

      {/* Title */}
      <Typography
        variant="h6"
        sx={{
          color: 'text.secondary',
          fontWeight: typographyTokens.fontWeight.semibold,
          fontSize: compact ? typographyTokens.fontSize.base : typographyTokens.fontSize.lg,
          mb: description ? 1 : 0,
        }}
      >
        {title}
      </Typography>

      {/* Description */}
      {description && (
        <Typography
          variant="body2"
          sx={{
            color: 'text.secondary',
            fontSize: typographyTokens.fontSize.sm,
            maxWidth: 400,
            mb: action ? 3 : 0,
          }}
        >
          {description}
        </Typography>
      )}

      {/* Action */}
      {action && (
        <Box sx={{ mt: action ? 0 : 3 }}>
          {action}
        </Box>
      )}
    </Box>
  )
}
