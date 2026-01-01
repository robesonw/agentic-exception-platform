/**
 * CardGrid Component
 * 
 * A responsive CSS grid for card layouts.
 * 
 * Specs:
 * - CSS Grid with auto-fit columns
 * - Gap: 24px
 * - Responsive columns (auto-fit, minmax)
 * - Equal-height cards (stretch)
 */

import { Box, type SxProps, type Theme } from '@mui/material'

export interface CardGridProps {
  /** Grid content (cards) */
  children: React.ReactNode
  /** Minimum card width (default: 280px) */
  minCardWidth?: number | string
  /** Number of columns (optional - uses auto-fit if not specified) */
  columns?: 1 | 2 | 3 | 4 | 5 | 6
  /** Gap between cards (default: 24px = 3) */
  gap?: number
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function CardGrid({
  children,
  minCardWidth = 280,
  columns,
  gap = 3,
  sx,
}: CardGridProps) {
  // Build grid template based on columns prop
  const gridTemplateColumns = columns
    ? `repeat(${columns}, 1fr)`
    : `repeat(auto-fit, minmax(${typeof minCardWidth === 'number' ? `${minCardWidth}px` : minCardWidth}, 1fr))`

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns,
        gap,
        alignItems: 'stretch', // Equal-height cards
        ...sx,
      }}
    >
      {children}
    </Box>
  )
}
