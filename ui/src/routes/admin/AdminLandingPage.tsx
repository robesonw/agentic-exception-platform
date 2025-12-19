import { useQuery } from '@tanstack/react-query'
import { Box, Grid, Card, CardContent, Typography, Link, CircularProgress, Alert } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { useTenant } from '../../hooks/useTenant'
import { listConfigChanges } from '../../api/admin'
import PageHeader from '../../components/common/PageHeader'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import SettingsIcon from '@mui/icons-material/Settings'
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings'
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck'
import BuildIcon from '@mui/icons-material/Build'

interface QuickLinkCardProps {
  title: string
  description: string
  to: string
  icon: React.ReactNode
  badge?: number
}

function QuickLinkCard({ title, description, to, icon, badge }: QuickLinkCardProps) {
  return (
    <Card
      component={RouterLink}
      to={to}
      sx={{
        height: '100%',
        textDecoration: 'none',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: 4,
        },
        cursor: 'pointer',
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          {icon}
          {badge !== undefined && badge > 0 && (
            <Box
              sx={{
                bgcolor: 'error.main',
                color: 'white',
                borderRadius: '50%',
                width: 24,
                height: 24,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                fontWeight: 600,
              }}
            >
              {badge}
            </Box>
          )}
        </Box>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {description}
        </Typography>
      </CardContent>
    </Card>
  )
}

export default function AdminLandingPage() {
  const { tenantId } = useTenant()

  const { data: pendingChanges, isLoading, isError, error } = useQuery({
    queryKey: ['config-changes-pending', tenantId],
    queryFn: () => listConfigChanges({ tenantId: tenantId || undefined, status: 'pending' }),
    enabled: !!tenantId,
    refetchInterval: 60000, // Refresh every minute
  })

  const pendingCount = pendingChanges?.items.length || 0

  // Handle 401/403 errors
  if (isError && error && 'status' in error && (error.status === 401 || error.status === 403)) {
    return <NotAuthorizedPage />
  }

  // Handle 429 rate limit errors
  if (isError && error && 'status' in error && error.status === 429) {
    return (
      <Box>
        <PageHeader
          title="Admin Dashboard"
          subtitle="Governance and configuration management"
        />
        <Alert severity="warning" sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            Rate Limit Exceeded
          </Typography>
          <Typography variant="body2">
            Too many requests. Please wait a minute before trying again.
          </Typography>
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Admin Dashboard"
        subtitle="Governance and configuration management"
      />
      
      <AdminWarningBanner />

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {/* Pending Approvals Summary */}
          {pendingCount > 0 && (
            <Alert severity="warning" sx={{ mb: 3 }}>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                {pendingCount} pending configuration change{pendingCount !== 1 ? 's' : ''} require approval
              </Typography>
              <Link component={RouterLink} to="/admin/config-changes" sx={{ mt: 1, display: 'block' }}>
                Review pending changes →
              </Link>
            </Alert>
          )}

          {/* Quick Links */}
          <Grid container spacing={3}>
            <Grid item xs={12} sm={6} md={4}>
              <QuickLinkCard
                title="Config Changes"
                description="Review and approve configuration change requests"
                to="/admin/config-changes"
                icon={<SettingsIcon sx={{ fontSize: 40, color: 'primary.main' }} />}
                badge={pendingCount}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <QuickLinkCard
                title="Packs"
                description="Manage Domain Packs and Tenant Policy Packs"
                to="/admin/packs"
                icon={<AdminPanelSettingsIcon sx={{ fontSize: 40, color: 'primary.main' }} />}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <QuickLinkCard
                title="Playbooks"
                description="View and manage playbook configurations"
                to="/admin/playbooks"
                icon={<PlaylistAddCheckIcon sx={{ fontSize: 40, color: 'primary.main' }} />}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <QuickLinkCard
                title="Tools"
                description="Manage tool registry and tenant enablement"
                to="/admin/tools"
                icon={<BuildIcon sx={{ fontSize: 40, color: 'primary.main' }} />}
              />
            </Grid>
          </Grid>
        </>
      )}
    </Box>
  )
}

