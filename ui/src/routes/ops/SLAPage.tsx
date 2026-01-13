import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Box, Alert, Chip, Typography, Tabs, Tab, Grid, Card, CardContent, FormControl, InputLabel, Select, MenuItem } from '@mui/material'
import PageHeader from '../../components/common/PageHeader'
import { useTenant } from '../../hooks/useTenant'
import { isOpsEnabled } from '../../utils/featureFlags'
import { getSLACompliance, getSLABreaches, getSLAAtRisk } from '../../api/ops'
import DataTable from '../../components/common/DataTable'
import OpsFilterBar from '../../components/common/OpsFilterBar'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { SLABreach, SLAAtRisk } from '../../api/ops'
import type { OpsFilters } from '../../components/common/OpsFilterBar'

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
      id={`sla-tabpanel-${index}`}
      aria-labelledby={`sla-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  )
}

export default function SLAPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const [tabValue, setTabValue] = useState(0)
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('day')
  const [filters, setFilters] = useState<OpsFilters>({})
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)

  if (!isOpsEnabled()) {
    return (
      <Box>
        <Alert severity="error">Ops features are not enabled. Set VITE_OPS_ENABLED=true in ui/.env</Alert>
      </Box>
    )
  }

  const { data: complianceData, isLoading: complianceLoading, dataUpdatedAt: complianceUpdatedAt } = useQuery({
    queryKey: ['sla-compliance', tenantId, period],
    queryFn: () => getSLACompliance({ tenantId: tenantId || undefined, period }),
    enabled: !!tenantId,
    refetchInterval: 60000,
  })

  const { data: breachesData, isLoading: breachesLoading, dataUpdatedAt: breachesUpdatedAt } = useQuery({
    queryKey: ['sla-breaches', tenantId, filters, page, pageSize],
    queryFn: () => getSLABreaches({
      tenantId: tenantId || undefined,
      domain: filters.domain,
      exceptionType: filters.eventType,
      from: filters.dateFrom,
      to: filters.dateTo,
      limit: pageSize,
      offset: page * pageSize,
    }),
    enabled: !!tenantId,
  })

  const { data: atRiskData, isLoading: atRiskLoading, dataUpdatedAt: atRiskUpdatedAt } = useQuery({
    queryKey: ['sla-at-risk', tenantId],
    queryFn: () => getSLAAtRisk({ tenantId: tenantId || undefined }),
    enabled: !!tenantId,
    refetchInterval: 30000,
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['sla-compliance', tenantId] })
    queryClient.invalidateQueries({ queryKey: ['sla-breaches', tenantId] })
    queryClient.invalidateQueries({ queryKey: ['sla-at-risk', tenantId] })
  }

  const lastUpdated = tabValue === 0
    ? (breachesUpdatedAt ? new Date(breachesUpdatedAt) : undefined)
    : (atRiskUpdatedAt ? new Date(atRiskUpdatedAt) : undefined)

  const breachesColumns: DataTableColumn<SLABreach>[] = [
    {
      id: 'exceptionId',
      label: 'Exception ID',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.exceptionId}
        </Typography>
      ),
    },
    {
      id: 'domain',
      label: 'Domain',
      accessor: (row) => row.domain,
    },
    {
      id: 'exceptionType',
      label: 'Exception Type',
      accessor: (row) => row.exceptionType,
    },
    {
      id: 'severity',
      label: 'Severity',
      accessor: (row) => (
        <Chip
          label={row.severity}
          size="small"
          color={row.severity === 'CRITICAL' ? 'error' : row.severity === 'HIGH' ? 'warning' : 'default'}
        />
      ),
    },
    {
      id: 'breachTimestamp',
      label: 'Breach Time',
      accessor: (row) => new Date(row.breachTimestamp).toLocaleString(),
    },
    {
      id: 'slaDeadline',
      label: 'SLA Deadline',
      accessor: (row) => new Date(row.slaDeadline).toLocaleString(),
    },
  ]

  const atRiskColumns: DataTableColumn<SLAAtRisk>[] = [
    {
      id: 'exceptionId',
      label: 'Exception ID',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.exceptionId}
        </Typography>
      ),
    },
    {
      id: 'domain',
      label: 'Domain',
      accessor: (row) => row.domain,
    },
    {
      id: 'exceptionType',
      label: 'Exception Type',
      accessor: (row) => row.exceptionType,
    },
    {
      id: 'severity',
      label: 'Severity',
      accessor: (row) => (
        <Chip
          label={row.severity}
          size="small"
          color={row.severity === 'CRITICAL' ? 'error' : row.severity === 'HIGH' ? 'warning' : 'default'}
        />
      ),
    },
    {
      id: 'timeUntilDeadline',
      label: 'Time Until Deadline',
      accessor: (row) => row.timeUntilDeadline,
    },
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view SLA compliance data.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="SLA Compliance & Breaches"
        subtitle="Monitor SLA compliance rates and breach incidents"
        lastUpdated={lastUpdated}
        onRefresh={handleRefresh}
        actions={
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Period</InputLabel>
            <Select
              value={period}
              label="Period"
              onChange={(e) => setPeriod(e.target.value as 'day' | 'week' | 'month')}
            >
              <MenuItem value="day">Day</MenuItem>
              <MenuItem value="week">Week</MenuItem>
              <MenuItem value="month">Month</MenuItem>
            </Select>
          </FormControl>
        }
      />

      {/* Compliance Summary Card */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Compliance Rate
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 700 }}>
                {complianceLoading ? '...' : `${((complianceData?.complianceRate || 0) * 100).toFixed(1)}%`}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {period} period
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Breaches
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, color: 'error.main' }}>
                {breachesLoading ? '...' : breachesData?.total || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total breaches
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                At Risk
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, color: 'warning.main' }}>
                {atRiskLoading ? '...' : atRiskData?.total || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Exceptions at risk
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)} sx={{ mb: 2 }}>
        <Tab label="Breaches" />
        <Tab label="At Risk" />
      </Tabs>

      <TabPanel value={tabValue} index={0}>
        <OpsFilterBar
          value={filters}
          onChange={setFilters}
          showDateRange={true}
          showDomain={true}
          showEventType={true}
          syncWithUrl={true}
        />
        <DataTable
          columns={breachesColumns as DataTableColumn<Record<string, unknown>>[]}
          rows={(breachesData?.breaches || []) as Record<string, unknown>[]}
          loading={breachesLoading}
          page={page}
          pageSize={pageSize}
          totalCount={breachesData?.total || 0}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
          emptyTitle="No SLA breaches"
          emptyMessage="No SLA breaches found in the selected time range."
        />
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        <DataTable
          columns={atRiskColumns as DataTableColumn<Record<string, unknown>>[]}
          rows={(atRiskData?.atRisk || []) as Record<string, unknown>[]}
          loading={atRiskLoading}
          page={page}
          pageSize={pageSize}
          totalCount={atRiskData?.total || 0}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
          emptyTitle="No exceptions at risk"
          emptyMessage="No exceptions are currently at risk of SLA breach."
        />
      </TabPanel>
    </Box>
  )
}

