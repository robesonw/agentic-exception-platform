import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Alert,
  Chip,
  Typography,
  Button,
  Stack,
  Drawer,
  IconButton,
  Grid,
  Divider,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import CloseIcon from '@mui/icons-material/Close'
import PageHeader from '../../components/common/PageHeader'
import { useTenant } from '../../hooks/useTenant'
import { isOpsEnabled } from '../../utils/featureFlags'
import { getAlertHistory, acknowledgeAlert, resolveAlert } from '../../api/ops'
import DataTable from '../../components/common/DataTable'
import OpsFilterBar from '../../components/common/OpsFilterBar'
import CodeViewer from '../../components/common/CodeViewer'
import { useSnackbar } from '../../components/common/SnackbarProvider'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { AlertHistory } from '../../api/ops'
import type { OpsFilters } from '../../components/common/OpsFilterBar'

export default function AlertsHistoryPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const { showSuccess, showError } = useSnackbar()
  const [filters, setFilters] = useState<OpsFilters>({})
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [selectedAlert, setSelectedAlert] = useState<AlertHistory | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  if (!isOpsEnabled()) {
    return (
      <Box>
        <Alert severity="error">Ops features are not enabled. Set VITE_OPS_ENABLED=true in ui/.env</Alert>
      </Box>
    )
  }

  const { data: historyData, isLoading: historyLoading, dataUpdatedAt } = useQuery({
    queryKey: ['alert-history', tenantId, filters, page, pageSize],
    queryFn: () => getAlertHistory({
      tenantId: tenantId || '',
      alertType: filters.eventType,
      status: filters.status,
      severity: filters.severity,
      from: filters.dateFrom,
      to: filters.dateTo,
      limit: pageSize,
      offset: page * pageSize,
    }),
    enabled: !!tenantId,
    refetchInterval: 30000,
  })

  const acknowledgeMutation = useMutation({
    mutationFn: (id: string) => acknowledgeAlert(id, tenantId || ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-history', tenantId] })
      showSuccess('Alert acknowledged successfully')
    },
    onError: (error) => {
      showError(`Failed to acknowledge alert: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const resolveMutation = useMutation({
    mutationFn: (id: string) => resolveAlert(id, tenantId || ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-history', tenantId] })
      showSuccess('Alert resolved successfully')
    },
    onError: (error) => {
      showError(`Failed to resolve alert: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['alert-history', tenantId] })
  }

  const handleRowClick = (alert: AlertHistory) => {
    setSelectedAlert(alert)
    setDrawerOpen(true)
  }

  const handleAcknowledge = (id: string) => {
    acknowledgeMutation.mutate(id)
  }

  const handleResolve = (id: string) => {
    resolveMutation.mutate(id)
  }

  const columns: DataTableColumn<AlertHistory>[] = [
    {
      id: 'id',
      label: 'Alert ID',
      accessor: (row) => (
        <Typography
          variant="body2"
          sx={{ fontFamily: 'monospace', fontSize: '0.75rem', cursor: 'pointer', textDecoration: 'underline', color: 'primary.main' }}
          onClick={() => handleRowClick(row)}
        >
          {row.id.substring(0, 8)}...
        </Typography>
      ),
    },
    {
      id: 'alertType',
      label: 'Alert Type',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.alertType.replace(/_/g, ' ')}
        </Typography>
      ),
    },
    {
      id: 'severity',
      label: 'Severity',
      accessor: (row) => (
        <Chip
          label={row.severity}
          size="small"
          color={
            row.severity === 'CRITICAL' ? 'error' :
            row.severity === 'HIGH' ? 'warning' : 'default'
          }
        />
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
            row.status === 'resolved' ? 'success' :
            row.status === 'acknowledged' ? 'info' : 'error'
          }
        />
      ),
    },
    {
      id: 'domain',
      label: 'Domain',
      accessor: (row) => row.domain || '-',
    },
    {
      id: 'triggeredAt',
      label: 'Triggered At',
      accessor: (row) => new Date(row.triggeredAt).toLocaleString(),
    },
    {
      id: 'acknowledgedAt',
      label: 'Acknowledged',
      accessor: (row) => row.acknowledgedAt ? new Date(row.acknowledgedAt).toLocaleString() : '-',
    },
    {
      id: 'resolvedAt',
      label: 'Resolved',
      accessor: (row) => row.resolvedAt ? new Date(row.resolvedAt).toLocaleString() : '-',
    },
    {
      id: 'actions',
      label: 'Actions',
      accessor: (row) => (
        <Stack direction="row" spacing={1}>
          {row.status === 'fired' && (
            <Button
              size="small"
              variant="outlined"
              onClick={() => handleAcknowledge(row.id)}
              disabled={acknowledgeMutation.isPending}
            >
              Acknowledge
            </Button>
          )}
          {row.status !== 'resolved' && (
            <Button
              size="small"
              variant="contained"
              startIcon={<CheckCircleIcon />}
              onClick={() => handleResolve(row.id)}
              disabled={resolveMutation.isPending}
            >
              Resolve
            </Button>
          )}
        </Stack>
      ),
    },
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view alert history.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Alerts History"
        subtitle="View alert history and manage alert status"
        lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : undefined}
        onRefresh={handleRefresh}
      />

      <OpsFilterBar
        value={filters}
        onChange={setFilters}
        showDateRange={true}
        showStatus={true}
        showEventType={true}
        showSeverity={true}
        syncWithUrl={true}
      />

      <DataTable
        columns={columns as DataTableColumn<Record<string, unknown>>[]}
        rows={(historyData?.items || []) as Record<string, unknown>[]}
        loading={historyLoading}
        page={page}
        pageSize={pageSize}
        totalCount={historyData?.total || 0}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        emptyTitle="No alerts fired"
        emptyMessage="No alerts fired in selected range."
      />

      {/* Detail Drawer */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedAlert(null)
        }}
        PaperProps={{
          sx: { width: { xs: '100%', sm: 600 } },
        }}
      >
        <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6">Alert Details</Typography>
            <IconButton onClick={() => {
              setDrawerOpen(false)
              setSelectedAlert(null)
            }}>
              <CloseIcon />
            </IconButton>
          </Box>

          {selectedAlert ? (
            <>
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Alert ID</Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {selectedAlert.id}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Alert Type</Typography>
                  <Typography variant="body2">{selectedAlert.alertType.replace(/_/g, ' ')}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Status</Typography>
                  <Box>
                    <Chip
                      label={selectedAlert.status}
                      size="small"
                      color={
                        selectedAlert.status === 'resolved' ? 'success' :
                        selectedAlert.status === 'acknowledged' ? 'info' : 'error'
                      }
                    />
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Severity</Typography>
                  <Box>
                    <Chip
                      label={selectedAlert.severity}
                      size="small"
                      color={
                        selectedAlert.severity === 'CRITICAL' ? 'error' :
                        selectedAlert.severity === 'HIGH' ? 'warning' : 'default'
                      }
                    />
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Domain</Typography>
                  <Typography variant="body2">{selectedAlert.domain || '-'}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Triggered At</Typography>
                  <Typography variant="body2">{new Date(selectedAlert.triggeredAt).toLocaleString()}</Typography>
                </Grid>
                {selectedAlert.acknowledgedAt && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="text.secondary">Acknowledged At</Typography>
                    <Typography variant="body2">{new Date(selectedAlert.acknowledgedAt).toLocaleString()}</Typography>
                  </Grid>
                )}
                {selectedAlert.resolvedAt && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="text.secondary">Resolved At</Typography>
                    <Typography variant="body2">{new Date(selectedAlert.resolvedAt).toLocaleString()}</Typography>
                  </Grid>
                )}
              </Grid>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" sx={{ mb: 1 }}>Payload</Typography>
              <CodeViewer code={selectedAlert.payload || {}} maxHeight={300} collapsible defaultCollapsed />

              <Divider sx={{ my: 3 }} />

              <Stack direction="row" spacing={2}>
                {selectedAlert.status === 'fired' && (
                  <Button
                    variant="outlined"
                    onClick={() => {
                      acknowledgeMutation.mutate(selectedAlert.id)
                      setDrawerOpen(false)
                      setSelectedAlert(null)
                    }}
                    disabled={acknowledgeMutation.isPending}
                  >
                    Acknowledge
                  </Button>
                )}
                {selectedAlert.status !== 'resolved' && (
                  <Button
                    variant="contained"
                    startIcon={<CheckCircleIcon />}
                    onClick={() => {
                      resolveMutation.mutate(selectedAlert.id)
                      setDrawerOpen(false)
                      setSelectedAlert(null)
                    }}
                    disabled={resolveMutation.isPending}
                  >
                    Resolve
                  </Button>
                )}
              </Stack>
            </>
          ) : (
            <Alert severity="info">No alert selected.</Alert>
          )}
        </Box>
      </Drawer>
    </Box>
  )
}

