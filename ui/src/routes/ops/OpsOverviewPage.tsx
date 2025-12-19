import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Box, Grid, Card, CardContent, Typography, Link, CircularProgress, Alert } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { useTenant } from '../../hooks/useTenant'
import {
  getWorkerHealth,
  getWorkerThroughput,
  getSLACompliance,
  getSLAAtRisk,
  listDLQEntries,
  getAlertHistory,
  listAuditReports,
} from '../../api/ops'
import PageHeader from '../../components/common/PageHeader'
import ErrorIcon from '@mui/icons-material/Error'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import WarningIcon from '@mui/icons-material/Warning'

interface MetricWidgetProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: React.ReactNode
  color?: 'primary' | 'success' | 'warning' | 'error'
  linkTo?: string
}

function MetricWidget({ title, value, subtitle, icon, color = 'primary', linkTo }: MetricWidgetProps) {
  const content = (
    <Card
      sx={{
        height: '100%',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': linkTo ? { transform: 'translateY(-4px)', boxShadow: 4 } : {},
        cursor: linkTo ? 'pointer' : 'default',
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 600 }}>
            {title}
          </Typography>
          {icon}
        </Box>
        <Typography variant="h4" sx={{ fontWeight: 700, color: `${color}.main` }}>
          {value}
        </Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {subtitle}
          </Typography>
        )}
        {linkTo && (
          <Link
            component={RouterLink}
            to={linkTo}
            sx={{ mt: 1, display: 'inline-block', fontSize: '0.875rem' }}
          >
            View details →
          </Link>
        )}
      </CardContent>
    </Card>
  )

  return content
}

export default function OpsOverviewPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()

  // Fetch all metrics
  const { data: workerHealth, isLoading: healthLoading, dataUpdatedAt: healthUpdatedAt } = useQuery({
    queryKey: ['worker-health'],
    queryFn: getWorkerHealth,
    refetchInterval: 30000, // Refresh every 30s
  })

  const { data: workerThroughput, isLoading: throughputLoading, dataUpdatedAt: throughputUpdatedAt } = useQuery({
    queryKey: ['worker-throughput'],
    queryFn: getWorkerThroughput,
    refetchInterval: 30000,
  })

  const { data: slaCompliance, isLoading: slaLoading, dataUpdatedAt: slaUpdatedAt } = useQuery({
    queryKey: ['sla-compliance', tenantId],
    queryFn: () => getSLACompliance({ tenantId: tenantId || undefined }),
    enabled: !!tenantId,
    refetchInterval: 60000, // Refresh every minute
  })

  const { data: slaAtRisk, isLoading: atRiskLoading, dataUpdatedAt: atRiskUpdatedAt } = useQuery({
    queryKey: ['sla-at-risk', tenantId],
    queryFn: () => getSLAAtRisk({ tenantId: tenantId || undefined }),
    enabled: !!tenantId,
    refetchInterval: 60000,
  })

  const { data: dlqData, isLoading: dlqLoading, dataUpdatedAt: dlqUpdatedAt } = useQuery({
    queryKey: ['dlq-summary', tenantId],
    queryFn: () => listDLQEntries({ tenantId: tenantId || '', limit: 1 }),
    enabled: !!tenantId,
    refetchInterval: 30000,
  })

  const { data: alertsData, isLoading: alertsLoading, dataUpdatedAt: alertsUpdatedAt } = useQuery({
    queryKey: ['alerts-summary', tenantId],
    queryFn: () => getAlertHistory({ tenantId: tenantId || '', limit: 10 }),
    enabled: !!tenantId,
    refetchInterval: 60000,
  })

  const { data: reportsData, isLoading: reportsLoading, dataUpdatedAt: reportsUpdatedAt } = useQuery({
    queryKey: ['reports-summary', tenantId],
    queryFn: () => listAuditReports({ tenantId: tenantId || '', limit: 10 }),
    enabled: !!tenantId,
    refetchInterval: 60000,
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['worker-health'] })
    queryClient.invalidateQueries({ queryKey: ['worker-throughput'] })
    queryClient.invalidateQueries({ queryKey: ['sla-compliance', tenantId] })
    queryClient.invalidateQueries({ queryKey: ['sla-at-risk', tenantId] })
    queryClient.invalidateQueries({ queryKey: ['dlq-summary', tenantId] })
    queryClient.invalidateQueries({ queryKey: ['alerts-summary', tenantId] })
    queryClient.invalidateQueries({ queryKey: ['reports-summary', tenantId] })
  }

  // Get the most recent dataUpdatedAt
  const lastUpdatedTimestamp = Math.max(
    healthUpdatedAt || 0,
    throughputUpdatedAt || 0,
    slaUpdatedAt || 0,
    atRiskUpdatedAt || 0,
    dlqUpdatedAt || 0,
    alertsUpdatedAt || 0,
    reportsUpdatedAt || 0
  )
  const lastUpdated = lastUpdatedTimestamp > 0 ? new Date(lastUpdatedTimestamp) : undefined

  const isLoading = healthLoading || throughputLoading || slaLoading || atRiskLoading || dlqLoading || alertsLoading || reportsLoading

  // Calculate metrics
  const healthyWorkers = workerHealth?.workers.filter((w) => w.status === 'healthy').length || 0
  const degradedWorkers = workerHealth?.workers.filter((w) => w.status === 'degraded').length || 0
  const unhealthyWorkers = workerHealth?.workers.filter((w) => w.status === 'unhealthy').length || 0
  const totalWorkers = workerHealth?.workers.length || 0

  const totalThroughput = workerThroughput?.throughput.reduce((sum, t) => sum + t.eventsPerSecond, 0) || 0
  const avgErrorRate = workerThroughput?.throughput.length
    ? workerThroughput.throughput.reduce((sum, t) => sum + (t.errorRate || 0), 0) / workerThroughput.throughput.length
    : 0

  const dlqSize = dlqData?.total || 0
  const alertsFired24h = alertsData?.items.filter((a) => {
    const triggeredAt = new Date(a.triggeredAt)
    const now = new Date()
    return now.getTime() - triggeredAt.getTime() < 24 * 60 * 60 * 1000
  }).length || 0

  const reportJobsQueued = reportsData?.items.filter((r) => r.status === 'queued' || r.status === 'generating').length || 0
  const reportJobsCompleted = reportsData?.items.filter((r) => r.status === 'completed').length || 0
  const reportJobsFailed = reportsData?.items.filter((r) => r.status === 'failed').length || 0

  // Health summary metrics
  const slaBreachedCount = slaAtRisk?.total || 0

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view operations data.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Operations Overview"
        subtitle="Real-time view of system health, throughput, and operational metrics"
        lastUpdated={lastUpdated}
        onRefresh={handleRefresh}
      />

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {/* Health Summary Section */}
          <Box sx={{ mb: 4 }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
              Health Summary
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Workers Healthy
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 700, color: 'success.main' }}>
                      {totalWorkers > 0 ? `${healthyWorkers}/${totalWorkers}` : '—'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {degradedWorkers > 0 && `${degradedWorkers} degraded`}
                      {degradedWorkers > 0 && unhealthyWorkers > 0 && ', '}
                      {unhealthyWorkers > 0 && `${unhealthyWorkers} unhealthy`}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      SLA Breached
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 700, color: slaBreachedCount > 0 ? 'error.main' : 'text.primary' }}>
                      {slaAtRisk ? slaBreachedCount : '—'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      exceptions at risk
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      DLQ Size
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 700, color: dlqSize > 0 ? 'error.main' : 'text.primary' }}>
                      {dlqData ? dlqSize : '—'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      failed events
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Alerts Fired (24h)
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 700, color: alertsFired24h > 0 ? 'warning.main' : 'text.primary' }}>
                      {alertsData ? alertsFired24h : '—'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      last 24 hours
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Box>

          {/* Main Metrics Grid */}
          <Grid container spacing={3}>
          {/* Worker Health */}
          <Grid item xs={12} sm={6} md={3}>
            <MetricWidget
              title="Worker Health"
              value={`${healthyWorkers}/${totalWorkers}`}
              subtitle={`${degradedWorkers} degraded, ${unhealthyWorkers} unhealthy`}
              icon={<CheckCircleIcon color="success" />}
              color={unhealthyWorkers > 0 ? 'error' : degradedWorkers > 0 ? 'warning' : 'success'}
              linkTo="/ops/workers"
            />
          </Grid>

          {/* Throughput */}
          <Grid item xs={12} sm={6} md={3}>
            <MetricWidget
              title="Throughput"
              value={`${totalThroughput.toFixed(1)}`}
              subtitle="events/min"
              color="primary"
              linkTo="/ops/workers"
            />
          </Grid>

          {/* Error Rate */}
          <Grid item xs={12} sm={6} md={3}>
            <MetricWidget
              title="Error Rate"
              value={`${(avgErrorRate * 100).toFixed(2)}%`}
              subtitle="average across workers"
              icon={avgErrorRate > 0.05 ? <ErrorIcon color="error" /> : <CheckCircleIcon color="success" />}
              color={avgErrorRate > 0.05 ? 'error' : avgErrorRate > 0.01 ? 'warning' : 'success'}
              linkTo="/ops/workers"
            />
          </Grid>

          {/* SLA Compliance */}
          <Grid item xs={12} sm={6} md={3}>
            <MetricWidget
              title="SLA Compliance"
              value={`${((slaCompliance?.complianceRate || 0) * 100).toFixed(1)}%`}
              subtitle={slaCompliance?.period || 'day'}
              icon={(slaCompliance?.complianceRate || 0) < 0.95 ? <WarningIcon color="warning" /> : <CheckCircleIcon color="success" />}
              color={(slaCompliance?.complianceRate || 0) < 0.95 ? 'warning' : 'success'}
              linkTo="/ops/sla"
            />
          </Grid>

          {/* SLA Breached */}
          <Grid item xs={12} sm={6} md={3}>
            <MetricWidget
              title="SLA Breached"
              value={slaAtRisk?.total || 0}
              subtitle="exceptions"
              icon={<ErrorIcon color="error" />}
              color="error"
              linkTo="/ops/sla"
            />
          </Grid>

          {/* DLQ Size */}
          <Grid item xs={12} sm={6} md={3}>
            <MetricWidget
              title="DLQ Size"
              value={dlqSize}
              subtitle="failed events"
              icon={dlqSize > 0 ? <ErrorIcon color="error" /> : <CheckCircleIcon color="success" />}
              color={dlqSize > 0 ? 'error' : 'success'}
              linkTo="/ops/dlq"
            />
          </Grid>

          {/* Alerts Fired */}
          <Grid item xs={12} sm={6} md={3}>
            <MetricWidget
              title="Alerts Fired"
              value={alertsFired24h}
              subtitle="last 24h"
              icon={alertsFired24h > 0 ? <WarningIcon color="warning" /> : <CheckCircleIcon color="success" />}
              color={alertsFired24h > 0 ? 'warning' : 'success'}
              linkTo="/ops/alerts/history"
            />
          </Grid>

          {/* Report Jobs */}
          <Grid item xs={12} sm={6} md={3}>
            <MetricWidget
              title="Report Jobs"
              value={`${reportJobsQueued} queued`}
              subtitle={`${reportJobsCompleted} completed, ${reportJobsFailed} failed`}
              icon={reportJobsFailed > 0 ? <ErrorIcon color="error" /> : <CheckCircleIcon color="success" />}
              color={reportJobsFailed > 0 ? 'error' : reportJobsQueued > 0 ? 'warning' : 'success'}
              linkTo="/ops/reports"
            />
          </Grid>
        </Grid>
        </>
      )}
    </Box>
  )
}

