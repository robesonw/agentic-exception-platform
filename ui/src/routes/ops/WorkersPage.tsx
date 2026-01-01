import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Box, Alert, Chip, Typography, Tabs, Tab, CircularProgress } from '@mui/material'
import PageHeader from '../../components/common/PageHeader'
import { PageShell, Card } from '../../components/ui'
import { useTenant } from '../../hooks/useTenant'
import { isOpsEnabled } from '../../utils/featureFlags'
import { getWorkerHealth, getWorkerThroughput } from '../../api/ops'
import DataTable from '../../components/common/DataTable'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { WorkerHealth, WorkerThroughput } from '../../api/ops'

interface TabPanelProps {
  children?: React.ReactNode
  index: number
  value: number
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`workers-tabpanel-${index}`}
      aria-labelledby={`workers-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  )
}

export default function WorkersPage() {
  const queryClient = useQueryClient()
  const [tabValue, setTabValue] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [sortField, setSortField] = useState<string>('workerType')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')

  if (!isOpsEnabled()) {
    return (
      <Box>
        <Alert severity="error">Ops features are not enabled. Set VITE_OPS_ENABLED=true in ui/.env</Alert>
      </Box>
    )
  }

  const { data: healthData, isLoading: healthLoading, error: healthError, dataUpdatedAt: healthUpdatedAt } = useQuery({
    queryKey: ['worker-health'],
    queryFn: getWorkerHealth,
    refetchInterval: 30000, // Refresh every 30s
  })

  const { data: throughputData, isLoading: throughputLoading, error: throughputError, dataUpdatedAt: throughputUpdatedAt } = useQuery({
    queryKey: ['worker-throughput'],
    queryFn: getWorkerThroughput,
    refetchInterval: 30000,
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['worker-health'] })
    queryClient.invalidateQueries({ queryKey: ['worker-throughput'] })
  }

  const handleSortChange = (field: string, direction: 'asc' | 'desc') => {
    setSortField(field)
    setSortDirection(direction)
  }

  const lastUpdated = tabValue === 0 
    ? (healthUpdatedAt ? new Date(healthUpdatedAt) : undefined)
    : (throughputUpdatedAt ? new Date(throughputUpdatedAt) : undefined)

  const healthColumns: DataTableColumn<WorkerHealth>[] = [
    {
      id: 'workerType',
      label: 'Worker Type',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {row.workerType}
        </Typography>
      ),
    },
    {
      id: 'instanceId',
      label: 'Instance ID',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.instanceId}
        </Typography>
      ),
    },
    {
      id: 'status',
      label: 'Status',
      accessor: (row) => (
        <Chip
          label={row.status}
          size="small"
          color={
            row.status === 'healthy' ? 'success' : row.status === 'degraded' ? 'warning' : 'error'
          }
        />
      ),
    },
    {
      id: 'host',
      label: 'Host',
      accessor: (row) => row.host || '-',
    },
    {
      id: 'version',
      label: 'Version',
      accessor: (row) => row.version || '-',
    },
    {
      id: 'responseTime',
      label: 'Response Time',
      numeric: true,
      accessor: (row) => (row.responseTime ? `${row.responseTime}ms` : '-'),
    },
    {
      id: 'lastCheck',
      label: 'Last Check',
      accessor: (row) => new Date(row.lastCheck).toLocaleString(),
    },
  ]

  const throughputColumns: DataTableColumn<WorkerThroughput>[] = [
    {
      id: 'workerType',
      label: 'Worker Type',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {row.workerType}
        </Typography>
      ),
    },
    {
      id: 'eventsPerSecond',
      label: 'Events/sec',
      numeric: true,
      accessor: (row) => row.eventsPerSecond.toFixed(2),
    },
    {
      id: 'latencyP50',
      label: 'P50 Latency',
      numeric: true,
      accessor: (row) => (row.latencyP50 ? `${row.latencyP50}ms` : '-'),
    },
    {
      id: 'latencyP95',
      label: 'P95 Latency',
      numeric: true,
      accessor: (row) => (row.latencyP95 ? `${row.latencyP95}ms` : '-'),
    },
    {
      id: 'latencyP99',
      label: 'P99 Latency',
      numeric: true,
      accessor: (row) => (row.latencyP99 ? `${row.latencyP99}ms` : '-'),
    },
    {
      id: 'errorRate',
      label: 'Error Rate',
      numeric: true,
      accessor: (row) => (
        <Chip
          label={`${((row.errorRate || 0) * 100).toFixed(2)}%`}
          size="small"
          color={(row.errorRate || 0) > 0.05 ? 'error' : (row.errorRate || 0) > 0.01 ? 'warning' : 'default'}
        />
      ),
    },
  ]

  // Sort data client-side (since backend doesn't support sorting yet)
  const sortedHealthWorkers = [...(healthData?.workers || [])].sort((a, b) => {
    const aVal = (a as Record<string, unknown>)[sortField]
    const bVal = (b as Record<string, unknown>)[sortField]
    if (aVal === bVal) return 0
    if (aVal == null) return 1
    if (bVal == null) return -1
    const comparison = String(aVal).localeCompare(String(bVal))
    return sortDirection === 'asc' ? comparison : -comparison
  })

  const sortedThroughput = [...(throughputData?.throughput || [])].sort((a, b) => {
    const aVal = (a as Record<string, unknown>)[sortField]
    const bVal = (b as Record<string, unknown>)[sortField]
    if (aVal === bVal) return 0
    if (aVal == null) return 1
    if (bVal == null) return -1
    const comparison = String(aVal).localeCompare(String(bVal))
    return sortDirection === 'asc' ? comparison : -comparison
  })

  return (
    <PageShell>
      <PageHeader
        title="Workers Health & Status"
        subtitle="Monitor worker instances and their health metrics"
        lastUpdated={lastUpdated}
        onRefresh={handleRefresh}
      />

      <Card noPadding>
        <Box sx={{ px: 3, pt: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
            <Tab label="Health Status" />
            <Tab label="Throughput" />
          </Tabs>
        </Box>

        <Box sx={{ p: 0 }}>
          <TabPanel value={tabValue} index={0}>
            {healthError ? (
              <Alert severity="error" sx={{ m: 2 }}>Failed to load worker health data.</Alert>
            ) : (
              <DataTable
                columns={healthColumns as DataTableColumn<Record<string, unknown>>[]}
                rows={sortedHealthWorkers as Record<string, unknown>[]}
                loading={healthLoading}
                page={page}
                pageSize={pageSize}
                totalCount={sortedHealthWorkers.length}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
                sortField={sortField}
                sortDirection={sortDirection}
                onSortChange={handleSortChange}
                emptyTitle="No workers reporting"
                emptyMessage="No workers are currently reporting. Start worker containers to see heartbeats."
              />
            )}
          </TabPanel>

          <TabPanel value={tabValue} index={1}>
            {throughputError ? (
              <Alert severity="error" sx={{ m: 2 }}>Failed to load throughput data.</Alert>
            ) : (
              <DataTable
                columns={throughputColumns as DataTableColumn<Record<string, unknown>>[]}
                rows={sortedThroughput as Record<string, unknown>[]}
                loading={throughputLoading}
                page={page}
                pageSize={pageSize}
                totalCount={sortedThroughput.length}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
                sortField={sortField}
                sortDirection={sortDirection}
                onSortChange={handleSortChange}
                emptyTitle="No throughput data"
                emptyMessage="No throughput metrics available. Workers will report metrics once they start processing events."
              />
            )}
          </TabPanel>
        </Box>
      </Card>
    </PageShell>
  )
}

