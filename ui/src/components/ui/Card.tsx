/**
 * Card Component
 * 
 * A consistent card surface with:
 * - Theme-aware background (adapts to light/dark mode)
 * - Subtle border and shadow
 * - Rounded corners
 * - Optional header with title and actions
 * 
 * Use for containing blocks of content.
 */

import { Box, Typography, useTheme, type SxProps, type Theme } from '@mui/material'
import { radii, shadows, typographyScale } from '../../theme/tokens'

export interface CardProps {
  /** Card content */
  children: React.ReactNode
  /** Card title (displays in header) */
  title?: string
  /** Card subtitle */
  subtitle?: string
  /** Header actions */
  actions?: React.ReactNode
  /** Disable padding */
  noPadding?: boolean
  /** Padding size */
  padding?: 'sm' | 'md' | 'lg'
  /** Enable hover effect */
  hoverable?: boolean
  /** Click handler (makes card interactive) */
  onClick?: () => void
  /** Additional styles */
  sx?: SxProps<Theme>
}

const paddingMap = {
  sm: 1.5,   // 12px
  md: 2,     // 16px  
  lg: 2.5,   // 20px
}

export default function Card({
  children,
  title,
  subtitle,
  actions,
  noPadding = false,
  padding = 'lg',
  hoverable = false,
  onClick,
  sx,
}: CardProps) {
  const theme = useTheme()
  const isInteractive = onClick || hoverable

  return (
    <Box
      onClick={onClick}
      sx={{
        backgroundColor: 'background.paper',
        border: 1,
        borderColor: 'divider',
        borderRadius: `${radii.lg}px`,
        boxShadow: shadows.card,
        overflow: 'hidden',
        transition: 'box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease',
        cursor: isInteractive ? 'pointer' : 'default',
        ...(isInteractive && {
          '&:hover': {
            boxShadow: shadows.cardHover,
            borderColor: theme.palette.mode === 'dark' 
              ? 'rgba(148, 163, 184, 0.3)' 
              : 'rgba(148, 163, 184, 0.6)',
            transform: 'translateY(-1px)',
          },
        }),
        ...sx,
      }}
    >
      {(title || actions) && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: paddingMap[padding],
            py: paddingMap[padding] * 0.75,
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Box>
            {title && (
              <Typography
                variant="subtitle1"
                sx={{
                  ...typographyScale.cardTitle,
                  color: 'text.primary',
                }}
              >
                {title}
              </Typography>
            )}
            {subtitle && (
              <Typography
                variant="caption"
                sx={{
                  ...typographyScale.cardSubtitle,
                  color: 'text.secondary',
                }}
              >
                {subtitle}
              </Typography>
            )}
          </Box>
          {actions && (
            <Box sx={{ ml: 2, display: 'flex', gap: 1 }}>
              {actions}
            </Box>
          )}
        </Box>
      )}
      <Box sx={noPadding ? undefined : { p: paddingMap[padding] }}>
        {children}
      </Box>
    </Box>
  )
}
