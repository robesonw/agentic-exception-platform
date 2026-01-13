/**
 * Badge Component
 * 
 * Consistent badge/chip styles for status and severity indicators.
 * Uses MUI theme tokens for automatic light/dark mode support.
 */

import { Chip, type ChipProps, type SxProps, type Theme, useTheme } from '@mui/material'
import { severityColors, statusColors, radii, typography as typographyTokens } from '../../theme/tokens'

type BadgeVariant = 'severity' | 'status' | 'default' | 'outline'
type SeverityLevel = 'critical' | 'high' | 'medium' | 'low'
type StatusLevel = 'open' | 'analyzing' | 'in_progress' | 'resolved' | 'escalated' | 'closed'

export interface BadgeProps {
  /** Badge label */
  label: string
  /** Badge variant */
  variant?: BadgeVariant
  /** Severity level (when variant is 'severity') */
  severity?: SeverityLevel
  /** Status level (when variant is 'status') */
  status?: StatusLevel
  /** Size */
  size?: 'small' | 'medium'
  /** Icon at start */
  icon?: React.ReactNode
  /** Additional styles */
  sx?: SxProps<Theme>
}

// Map to normalize status labels
const normalizeStatus = (status: string): StatusLevel => {
  const lower = status.toLowerCase().replace(/[_\s-]/g, '_')
  if (lower === 'in_progress' || lower === 'inprogress') return 'in_progress'
  if (lower === 'analyzing') return 'analyzing'
  if (lower === 'resolved') return 'resolved'
  if (lower === 'escalated') return 'escalated'
  if (lower === 'closed') return 'closed'
  return 'open'
}

// Map to normalize severity labels
const normalizeSeverity = (severity: string): SeverityLevel => {
  const lower = severity.toLowerCase()
  if (lower === 'critical') return 'critical'
  if (lower === 'high') return 'high'
  if (lower === 'medium') return 'medium'
  return 'low'
}

export default function Badge({
  label,
  variant = 'default',
  severity,
  status,
  size = 'small',
  icon,
  sx,
}: BadgeProps) {
  const theme = useTheme()
  
  // Default colors using theme tokens
  let bgColor = theme.palette.action.hover
  let textColor = theme.palette.text.secondary
  let borderColor = theme.palette.divider

  if (variant === 'severity' && severity) {
    const level = normalizeSeverity(severity)
    const colors = severityColors[level]
    bgColor = colors.bg
    textColor = colors.text
    borderColor = colors.border
  } else if (variant === 'status' && status) {
    const level = normalizeStatus(status)
    const colors = statusColors[level]
    bgColor = colors.bg
    textColor = colors.text
    borderColor = colors.border
  } else if (variant === 'outline') {
    bgColor = 'transparent'
    borderColor = theme.palette.text.primary
  }

  return (
    <Chip
      label={label}
      size={size}
      icon={icon as ChipProps['icon']}
      sx={{
        backgroundColor: bgColor,
        color: textColor,
        border: `1px solid ${borderColor}`,
        borderRadius: `${radii.md}px`,
        fontWeight: typographyTokens.fontWeight.medium,
        fontSize: size === 'small' ? typographyTokens.fontSize.xs : typographyTokens.fontSize.sm,
        height: size === 'small' ? 24 : 28,
        '& .MuiChip-icon': {
          color: textColor,
          marginLeft: '6px',
        },
        ...sx,
      }}
    />
  )
}

// Export preset components for common use cases
export function SeverityBadge({ severity, size }: { severity: string; size?: 'small' | 'medium' }) {
  return (
    <Badge
      label={severity.toUpperCase()}
      variant="severity"
      severity={normalizeSeverity(severity)}
      size={size}
    />
  )
}

export function StatusBadge({ status, size }: { status: string; size?: 'small' | 'medium' }) {
  const normalizedStatus = normalizeStatus(status)
  const displayLabel = normalizedStatus.replace(/_/g, ' ').toUpperCase()
  return (
    <Badge
      label={displayLabel}
      variant="status"
      status={normalizedStatus}
      size={size}
    />
  )
}
