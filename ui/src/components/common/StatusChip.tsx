/**
 * Shared Status Chip Component
 * 
 * Displays exception resolution status with consistent colors.
 * Used across Exceptions list, detail, and Supervisor views.
 */

import { Chip, ChipProps } from '@mui/material'
import type { ExceptionStatus } from '../../types'

export interface StatusChipProps {
  /** Resolution status */
  status: ExceptionStatus | string | null | undefined
  /** Chip size */
  size?: 'small' | 'medium'
  /** Additional MUI Chip props */
  sx?: ChipProps['sx']
}

/**
 * Get status chip color
 */
function getStatusColor(status: string | null | undefined): ChipProps['color'] {
  switch (status) {
    case 'OPEN':
      return 'info'
    case 'IN_PROGRESS':
      return 'warning'
    case 'RESOLVED':
      return 'success'
    case 'ESCALATED':
      return 'error'
    case 'PENDING_APPROVAL':
      return 'secondary'
    default:
      return 'default'
  }
}

/**
 * Format status label for display (replace underscores with spaces)
 */
function formatStatusLabel(status: string | null | undefined): string {
  if (!status) {
    return 'Unknown'
  }
  return status.replace(/_/g, ' ')
}

/**
 * Status Chip Component
 * 
 * Displays exception resolution status with color-coded chip.
 */
export default function StatusChip({ status, size = 'small', sx }: StatusChipProps) {
  const color = getStatusColor(status)
  const label = formatStatusLabel(status)

  return (
    <Chip
      label={label}
      color={color}
      size={size}
      sx={sx}
    />
  )
}

