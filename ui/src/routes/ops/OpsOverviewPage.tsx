import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Box, CircularProgress, Alert, IconButton, Tooltip } from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
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
import { PageShell, Section, KpiGrid } from '../../components/layout'
import { StatCard } from '../../components/ui'

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
      <PageShell
        title="Operations Overview"
        subtitle="Real-time view of system health, throughput, and operational metrics"
      >
        <Alert severity="warning">Please select a tenant to view operations data.</Alert>
      </PageShell>
    )
  }

  // Format last updated for display
  const formatLastUpdated = () => {
    if (!lastUpdated) return null
    return lastUpdated.toLocaleString()
  }

  return (
    <PageShell
      title="Operations Overview"
      subtitle="Real-time view of system health, throughput, and operational metrics"
      actions={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {formatLastUpdated() && (
            <Box component="span" sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
              Updated: {formatLastUpdated()}
            </Box>
          )}
          <Tooltip title="Refresh all metrics">
            <IconButton onClick={handleRefresh} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      }
    >
      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {/* Health Summary Section */}
          <Section title="Health Summary">
            <KpiGrid>
              <StatCard
                label="Workers Healthy"
                value={totalWorkers > 0 ? `${healthyWorkers}/${totalWorkers}` : '—'}
                subtitle={degradedWorkers > 0 || unhealthyWorkers > 0
                  ? `${degradedWorkers} degraded${unhealthyWorkers > 0 ? `, ${unhealthyWorkers} unhealthy` : ''}`
                  : 'all systems operational'
                }
                variant={unhealthyWorkers > 0 ? 'error' : degradedWorkers > 0 ? 'warning' : 'success'}
              />
              <StatCard
                label="SLA Breached"
                value={slaAtRisk ? slaBreachedCount : '—'}
                subtitle="exceptions at risk"
                variant={slaBreachedCount > 0 ? 'error' : 'default'}
              />
              <StatCard
                label="DLQ Size"
                value={dlqData ? dlqSize : '—'}
                subtitle="failed events"
                variant={dlqSize > 0 ? 'error' : 'default'}
              />
              <StatCard
                label="Alerts (24h)"
                value={alertsData ? alertsFired24h : '—'}
                subtitle="last 24 hours"
                variant={alertsFired24h > 0 ? 'warning' : 'default'}
              />
            </KpiGrid>
          </Section>

          {/* Detailed Metrics Grid */}
          <Section title="Detailed Metrics" noMargin>
            <KpiGrid>
              <StatCard
                label="Worker Health"
                value={`${healthyWorkers}/${totalWorkers}`}
                subtitle={`${degradedWorkers} degraded, ${unhealthyWorkers} unhealthy`}
                variant={unhealthyWorkers > 0 ? 'error' : degradedWorkers > 0 ? 'warning' : 'success'}
              />
              <StatCard
                label="Throughput"
                value={`${totalThroughput.toFixed(1)}`}
                subtitle="events/min"
                variant="primary"
              />
              <StatCard
                label="Error Rate"
                value={`${(avgErrorRate * 100).toFixed(2)}%`}
                subtitle="average across workers"
                variant={avgErrorRate > 0.05 ? 'error' : avgErrorRate > 0.01 ? 'warning' : 'success'}
              />
              <StatCard
                label="SLA Compliance"
                value={`${((slaCompliance?.complianceRate || 0) * 100).toFixed(1)}%`}
                subtitle={slaCompliance?.period || 'day'}
                variant={(slaCompliance?.complianceRate || 0) < 0.95 ? 'warning' : 'success'}
              />
              <StatCard
                label="SLA Breached"
                value={slaAtRisk?.total || 0}
                subtitle="exceptions"
                variant="error"
              />
              <StatCard
                label="DLQ Size"
                value={dlqSize}
                subtitle="failed events"
                variant={dlqSize > 0 ? 'error' : 'success'}
              />
              <StatCard
                label="Alerts Fired"
                value={alertsFired24h}
                subtitle="last 24h"
                variant={alertsFired24h > 0 ? 'warning' : 'success'}
              />
              <StatCard
                label="Report Jobs"
                value={`${reportJobsQueued} queued`}
                subtitle={`${reportJobsCompleted} done, ${reportJobsFailed} failed`}
                variant={reportJobsFailed > 0 ? 'error' : reportJobsQueued > 0 ? 'warning' : 'success'}
              />
            </KpiGrid>
          </Section>
        </>
      )}
    </PageShell>
  )
}