import { Box, Stack, Typography, Divider } from '@mui/material'

export interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  children?: React.ReactNode
}

export default function PageHeader({ title, subtitle, actions, children }: PageHeaderProps) {

  return (
    <Box sx={{ mb: 3 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={2}
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        justifyContent="space-between"
        sx={{ mb: subtitle || children ? 1.5 : 0 }}
      >
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h4" component="h1" gutterBottom={!!subtitle}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="subtitle1" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        {actions && (
          <Box
            sx={{
              display: 'flex',
              gap: 1,
              flexWrap: 'wrap',
              width: { xs: '100%', sm: 'auto' },
              justifyContent: { xs: 'flex-start', sm: 'flex-end' },
            }}
          >
            {actions}
          </Box>
        )}
      </Stack>
      {children && <Box sx={{ mt: 1.5 }}>{children}</Box>}
      <Divider sx={{ mt: 2 }} />
    </Box>
  )
}

