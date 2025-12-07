/**
 * Shared Severity Chip Component
 * 
 * Displays exception severity with consistent colors and optional icons.
 * Used across Exceptions list, detail, and Supervisor views.
 */

import { Chip, ChipProps } from '@mui/material'
import { Error as ErrorIcon, Warning as WarningIcon } from '@mui/icons-material'
import type { ExceptionSeverity } from '../../types'

export interface SeverityChipProps {
  /** Severity level */
  severity: ExceptionSeverity | string | null | undefined
  /** Chip size */
  size?: 'small' | 'medium'
  /** Additional MUI Chip props */
  sx?: ChipProps['sx']
}

/**
 * Get severity chip color
 */
function getSeverityColor(severity: string | null | undefined): ChipProps['color'] {
  switch (severity) {
    case 'CRITICAL':
      return 'error'
    case 'HIGH':
      return 'warning'
    case 'MEDIUM':
      return 'info'
    case 'LOW':
      return 'success'
    default:
      return 'default'
  }
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
 * Get icon for severity (only for HIGH and CRITICAL)
 */
function getSeverityIcon(severity: string | null | undefined) {
  switch (severity) {
    case 'CRITICAL':
      return <ErrorIcon fontSize="small" />
    case 'HIGH':
      return <WarningIcon fontSize="small" />
    default:
      return undefined
  }
}

/**
 * Severity Chip Component
 * 
 * Displays exception severity with color-coded chip and optional icons.
 */
export default function SeverityChip({ severity, size = 'small', sx }: SeverityChipProps) {
  const color = getSeverityColor(severity)
  const label = formatSeverityLabel(severity)
  const icon = getSeverityIcon(severity)

  return (
    <Chip
      label={label}
      color={color}
      size={size}
      icon={icon}
      sx={sx}
    />
  )
}

