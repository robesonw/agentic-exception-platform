/**
 * Empty State Component
 * 
 * Displays a friendly, consistent empty state message when no data is available.
 * Used across lists, tables, and detail views to provide helpful guidance.
 */

import { Box, Typography, Button } from '@mui/material'
import { Inbox as InboxIcon } from '@mui/icons-material'

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
        py: 6,
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
          color: 'text.secondary',
          mb: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        aria-hidden="true"
      >
        {icon || <InboxIcon sx={{ fontSize: 64, opacity: 0.5 }} />}
      </Box>

      {/* Title */}
      <Typography variant="h6" color="text.primary" gutterBottom sx={{ fontWeight: 500 }}>
        {title}
      </Typography>

      {/* Description */}
      {description && (
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 400, mb: action ? 3 : 0 }}>
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

