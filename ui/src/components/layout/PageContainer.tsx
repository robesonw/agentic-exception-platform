/**
 * PageContainer Component
 * 
 * The outermost layout wrapper for all page content.
 * Uses MUI theme tokens for automatic light/dark mode support.
 * Provides consistent padding and background.
 * 
 * Specs:
 * - Full width by default (fills available space)
 * - padding: 24px top/bottom, 32px left/right
 * - Theme-aware page background
 */

import { Box, type SxProps, type Theme } from '@mui/material'

export interface PageContainerProps {
  /** Page content */
  children: React.ReactNode
  /** Maximum width of content area (default: none - full width) */
  maxWidth?: number | string
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function PageContainer({
  children,
  maxWidth,
  sx,
}: PageContainerProps) {
  return (
    <Box
      component="main"
      sx={{
        minHeight: '100%',
        backgroundColor: 'background.default',
        py: 3,       // 24px vertical padding
        px: 4,       // 32px horizontal padding
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
