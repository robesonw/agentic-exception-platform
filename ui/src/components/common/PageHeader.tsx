import { Box, Stack, Typography, Divider, IconButton, Tooltip } from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'

export interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  children?: React.ReactNode
  lastUpdated?: Date | string | null
  onRefresh?: () => void
}

export default function PageHeader({ title, subtitle, actions, children, lastUpdated, onRefresh }: PageHeaderProps) {
  const formatLastUpdated = (date: Date | string | null | undefined): string | null => {
    if (!date) return null
    const d = typeof date === 'string' ? new Date(date) : date
    if (isNaN(d.getTime())) return null
    return d.toLocaleString()
  }

  const lastUpdatedStr = formatLastUpdated(lastUpdated)

  return (
    <Box sx={{ mb: 3 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={2}
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        justifyContent="space-between"
        sx={{ mb: subtitle || children || lastUpdatedStr ? 1.5 : 0 }}
      >
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h4" component="h1" gutterBottom={!!subtitle || !!lastUpdatedStr}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="subtitle1" color="text.secondary" gutterBottom={!!lastUpdatedStr}>
              {subtitle}
            </Typography>
          )}
          {lastUpdatedStr && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              Last updated: {lastUpdatedStr}
            </Typography>
          )}
        </Box>
        <Box
          sx={{
            display: 'flex',
            gap: 1,
            flexWrap: 'wrap',
            width: { xs: '100%', sm: 'auto' },
            justifyContent: { xs: 'flex-start', sm: 'flex-end' },
            alignItems: 'center',
          }}
        >
          {onRefresh && (
            <Tooltip title="Refresh">
              <IconButton onClick={onRefresh} size="small">
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          )}
          {actions}
        </Box>
      </Stack>
      {children && <Box sx={{ mt: 1.5 }}>{children}</Box>}
      <Divider sx={{ mt: 2 }} />
    </Box>
  )
}

