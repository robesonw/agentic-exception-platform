/**
 * Empty State Component
 * 
 * Displays a friendly, consistent empty state message when no data is available.
 * Used across lists, tables, and detail views to provide helpful guidance.
 * Uses MUI theme tokens for automatic light/dark mode support.
 */

import { Box, Typography, Button } from '@mui/material'
import { Inbox as InboxIcon } from '@mui/icons-material'
import { typographyScale } from '../../theme/tokens'

export interface EmptyStateProps {
  /** Main title/heading */
  title?: string
  /** Descriptive text explaining why there's no data */
  description?: string
  /** Optional action button or element (e.g., "Clear filters" button) */
  action?: React.ReactNode
  /** Custom icon (defaults to Inbox icon) */
  icon?: React.ReactNode
  /** Additional CSS styling */
  sx?: Record<string, unknown>
}

/**
 * Empty State Component
 * 
 * Displays a centered, friendly message when no data is available.
 * Supports optional title, description, action button, and icon.
 */
export default function EmptyState({
  title = 'No data available',
  description,
  action,
  icon,
  sx,
}: EmptyStateProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        py: 8,
        px: 3,
        textAlign: 'center',
        ...sx,
      }}
      role="status"
      aria-live="polite"
    >
      {/* Icon - muted, not too large */}
      <Box
        sx={{
          color: 'text.disabled',
          mb: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        aria-hidden="true"
      >
        {icon || <InboxIcon sx={{ fontSize: 48 }} />}
      </Box>

      {/* Title - concise */}
      <Typography 
        sx={{ 
          ...typographyScale.cardTitle,
          color: 'text.secondary',
          mb: description ? 1 : 0,
        }}
      >
        {title}
      </Typography>

      {/* Description - optional, muted */}
      {description && (
        <Typography 
          sx={{ 
            ...typographyScale.bodySmall,
            color: 'text.secondary',
            maxWidth: 360,
            mb: action ? 3 : 0,
          }}
        >
          {description}
        </Typography>
      )}

      {/* Action Button */}
      {action && (
        <Box sx={{ mt: 2 }}>
          {typeof action === 'string' ? (
            <Button variant="outlined" size="small">
              {action}
            </Button>
          ) : (
            action
          )}
        </Box>
      )}
    </Box>
  )
}

