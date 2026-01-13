/**
 * PageShell Component
 * 
 * A layout wrapper for page content that provides consistent:
 * - Theme-aware background (adapts to light/dark mode)
 * - Full width by default (fills available space)
 * - Responsive horizontal padding (32px)
 * - Consistent vertical rhythm
 * 
 * Use this as the outer wrapper for all page content.
 */

import { Box, type SxProps, type Theme } from '@mui/material'

export interface PageShellProps {
  /** Page content */
  children: React.ReactNode
  /** Maximum width of content area (default: none - full width) */
  maxWidth?: number | string
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function PageShell({
  children,
  maxWidth,
  sx,
}: PageShellProps) {
  return (
    <Box
      sx={{
        minHeight: '100%',
        backgroundColor: 'background.default',
        py: 3,  // 24px vertical padding
        px: 4,  // 32px horizontal padding
        ...sx,
      }}
    >
      <Box
        sx={{
          width: '100%',
          maxWidth: maxWidth || 'none',
        }}
      >
        {children}
      </Box>
    </Box>
  )
}
