/**
 * KpiGrid Component
 * 
 * Responsive grid layout specifically for KPI/stat cards.
 * Enforces consistent column counts across breakpoints.
 * 
 * Features:
 * - Desktop (lg+): 4 columns
 * - Tablet (md): 2 columns  
 * - Mobile (sm-): 1 column
 * - Equal heights (CSS Grid stretch)
 * - Consistent 16px gap (tighter than content cards)
 * 
 * Usage:
 *   <KpiGrid>
 *     <StatCard label="Critical" value={3} />
 *     <StatCard label="Open" value={47} />
 *     <StatCard label="Resolution Rate" value="84%" />
 *     <StatCard label="Total" value={330} />
 *   </KpiGrid>
 * 
 * Note: For 3 KPIs, pass columns={3}. For 5+ KPIs, consider
 * multiple rows or different layout.
 */

import { Box, type SxProps, type Theme } from '@mui/material'

export interface KpiGridProps {
  /** KPI cards */
  children: React.ReactNode
  /** Override column count for all breakpoints */
  columns?: 1 | 2 | 3 | 4
  /** Gap between cards in spacing units (default: 2 = 16px) */
  gap?: number
  /** Additional styles */
  sx?: SxProps<Theme>
}

export default function KpiGrid({
  children,
  columns,
  gap = 2,
  sx,
}: KpiGridProps) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: columns
          ? `repeat(${columns}, 1fr)`
          : {
              xs: '1fr',                    // Mobile: 1 column
              sm: 'repeat(2, 1fr)',         // Small tablet: 2 columns
              md: 'repeat(2, 1fr)',         // Tablet: 2 columns
              lg: 'repeat(4, 1fr)',         // Desktop: 4 columns
            },
        gap,
        alignItems: 'stretch', // Equal-height cards
        ...sx,
      }}
    >
      {children}
    </Box>
  )
}
