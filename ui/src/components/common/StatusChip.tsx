/**
 * Shared Status Chip Component
 * 
 * Displays exception resolution status with muted enterprise colors.
 * Colors are informative, not aggressive - used as badges only.
 */

import { Chip, ChipProps } from '@mui/material'
import type { ExceptionStatus } from '../../types'
import { statusColors } from '../../theme/tokens'

export interface StatusChipProps {
  /** Resolution status */
  status: ExceptionStatus | string | null | undefined
  /** Chip size */
  size?: 'small' | 'medium'
  /** Additional MUI Chip props */
  sx?: ChipProps['sx']
}

type StatusKey = 'open' | 'analyzing' | 'in_progress' | 'resolved' | 'escalated' | 'closed'

/**
 * Normalize status to lowercase key
 */
function normalizeStatus(status: string | null | undefined): StatusKey {
  if (!status) return 'open'
  const lower = status.toLowerCase().replace(/[_\s-]/g, '_')
  if (lower === 'in_progress' || lower === 'inprogress') return 'in_progress'
  if (lower === 'analyzing' || lower === 'pending_approval') return 'analyzing'
  if (lower === 'resolved') return 'resolved'
  if (lower === 'escalated') return 'escalated'
  if (lower === 'closed') return 'closed'
  return 'open'
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
 * Displays exception resolution status with muted, enterprise-friendly colors.
 */
export default function StatusChip({ status, size = 'small', sx }: StatusChipProps) {
  const level = normalizeStatus(status)
  const colors = statusColors[level]
  const label = formatStatusLabel(status)

  return (
    <Chip
      label={label}
      size={size}
      sx={{
        backgroundColor: colors.bg,
        color: colors.text,
        border: `1px solid ${colors.border}`,
        fontWeight: 500,
        fontSize: size === 'small' ? '0.75rem' : '0.8125rem',
        ...sx,
      }}
    />
  )
}

