/**
 * Shared Severity Chip Component
 * 
 * Displays exception severity with consistent muted colors.
 * Colors are informative, not aggressive - used as badges only.
 */

import { Chip, ChipProps } from '@mui/material'
import type { ExceptionSeverity } from '../../types'
import { severityColors } from '../../theme/tokens'

export interface SeverityChipProps {
  /** Severity level */
  severity: ExceptionSeverity | string | null | undefined
  /** Chip size */
  size?: 'small' | 'medium'
  /** Additional MUI Chip props */
  sx?: ChipProps['sx']
}

/**
 * Normalize severity to lowercase key
 */
function normalizeSeverity(severity: string | null | undefined): 'critical' | 'high' | 'medium' | 'low' {
  if (!severity) return 'low'
  const lower = severity.toLowerCase()
  if (lower === 'critical') return 'critical'
  if (lower === 'high') return 'high'
  if (lower === 'medium') return 'medium'
  return 'low'
}

/**
 * Format severity label for display
 */
function formatSeverityLabel(severity: string | null | undefined): string {
  if (!severity) {
    return 'Unknown'
  }
  return severity
}

/**
 * Severity Chip Component
 * 
 * Displays exception severity with muted, enterprise-friendly colors.
 * No icons - clean badge style.
 */
export default function SeverityChip({ severity, size = 'small', sx }: SeverityChipProps) {
  const level = normalizeSeverity(severity)
  const colors = severityColors[level]
  const label = formatSeverityLabel(severity)

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

