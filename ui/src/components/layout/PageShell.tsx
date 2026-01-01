/**
 * PageShell Component
 * 
 * Full page layout wrapper providing consistent structure across all pages.
 * Uses MUI theme tokens for automatic light/dark mode support.
 * Combines container, header, and content area with proper vertical rhythm.
 * 
 * Features:
 * - Full-width content area with consistent horizontal padding (32px)
 * - Optional max-width constraint (default: none - full width)
 * - Integrated page header with title, subtitle, actions
 * - Consistent spacing: header → alerts → KPI → tables
 * - Theme-aware page background
 * 
 * Usage:
 *   <PageShell
 *     title="Operations Center"
 *     subtitle="Monitor and triage exceptions"
 *     actions={<Button>New Exception</Button>}
 *   >
 *     <AlertBanner />
 *     <KpiGrid>...</KpiGrid>
 *     <Section title="Exceptions">...</Section>
 *   </PageShell>
 * 
 * Vertical Rhythm (gaps between elements):
 * - Header to first child: 24px (handled by header mb)
 * - Alerts to KPI: 16px (handled by Alert component)
 * - KPI to tables: 32px (handled by Section component)
 */

import { Box, Typography, Stack, type SxProps, type Theme } from '@mui/material'
import { typography } from '../../theme/globalDesignSystem'

export interface PageShellProps {
  /** Page title (displayed in header) */
  title?: string
  /** Page subtitle/description */
  subtitle?: string
  /** Right-aligned action buttons */
  actions?: React.ReactNode
  /** Page content */
  children: React.ReactNode
  /** Maximum content width (default: none - full width) */
  maxWidth?: number | string
  /** Disable default padding */
  noPadding?: boolean
  /** Additional styles for outer container */
  sx?: SxProps<Theme>
}

export default function PageShell({
  title,
  subtitle,
  actions,
  children,
  maxWidth,
  noPadding = false,
  sx,
}: PageShellProps) {
  const hasHeader = title || actions

  return (
    <Box
      component="main"
      sx={{
        minHeight: '100%',
        backgroundColor: 'background.default',
        py: noPadding ? 0 : 3,  // 24px vertical padding
        px: noPadding ? 0 : 4,  // 32px horizontal padding
        ...sx,
      }}
    >
      <Box
        sx={{
          width: '100%',
          maxWidth: maxWidth || 'none',
        }}
      >
        {/* Page Header */}
        {hasHeader && (
          <Box sx={{ mb: 3 }}> {/* 24px margin to first content */}
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={2}
              alignItems={{ xs: 'flex-start', sm: 'center' }}
              justifyContent="space-between"
            >
              {/* Title + Subtitle Block (left-aligned) */}
              <Box sx={{ flexGrow: 1 }}>
                {title && (
                  <Typography
                    variant="h4"
                    component="h1"
                    sx={{
                      ...typography.pageTitle,
                      color: 'text.primary',
                      mb: subtitle ? 0.5 : 0,
                    }}
                  >
                    {title}
                  </Typography>
                )}
                {subtitle && (
                  <Typography
                    variant="body1"
                    sx={{
                      ...typography.pageSubtitle,
                      color: 'text.secondary',
                    }}
                  >
                    {subtitle}
                  </Typography>
                )}
              </Box>

              {/* Actions Block (right-aligned) */}
              {actions && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    flexShrink: 0,
                  }}
                >
                  {actions}
                </Box>
              )}
            </Stack>
          </Box>
        )}

        {/* Page Content */}
        {children}
      </Box>
    </Box>
  )
}
