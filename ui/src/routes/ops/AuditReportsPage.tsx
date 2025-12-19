import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Alert,
  Chip,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Paper,
  Drawer,
  IconButton,
  Stack,
  Divider,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DownloadIcon from '@mui/icons-material/Download'
import CloseIcon from '@mui/icons-material/Close'
import PageHeader from '../../components/common/PageHeader'
import { useTenant } from '../../hooks/useTenant'
import { isOpsEnabled } from '../../utils/featureFlags'
import { createAuditReport, listAuditReports, getAuditReport } from '../../api/ops'
import DataTable from '../../components/common/DataTable'
import CodeViewer from '../../components/common/CodeViewer'
import { useSnackbar } from '../../components/common/SnackbarProvider'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { AuditReport } from '../../api/ops'

export default function AuditReportsPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const { showSuccess, showError } = useSnackbar()
  const [requestDialogOpen, setRequestDialogOpen] = useState(false)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [selectedReport, setSelectedReport] = useState<AuditReport | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)

  const [requestForm, setRequestForm] = useState({
    reportType: 'exception_activity',
    domain: '',
    dateFrom: '',
    dateTo: '',
    format: 'csv' as 'csv' | 'json',
  })

  if (!isOpsEnabled()) {
    return (
      <Box>
        <Alert severity="error">Ops features are not enabled. Set VITE_OPS_ENABLED=true in ui/.env</Alert>
      </Box>
    )
  }

  const { data: reportsData, isLoading: reportsLoading, dataUpdatedAt } = useQuery({
    queryKey: ['audit-reports', tenantId, statusFilter, page, pageSize],
    queryFn: () => listAuditReports({
      tenantId: tenantId || '',
      status: statusFilter || undefined,
      limit: pageSize,
      offset: page * pageSize,
    }),
    enabled: !!tenantId,
    refetchInterval: 30000,
  })

  const createReportMutation = useMutation({
    mutationFn: (request: any) => createAuditReport(tenantId || '', request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audit-reports', tenantId] })
      setRequestDialogOpen(false)
      setRequestForm({
        reportType: 'exception_activity',
        domain: '',
        dateFrom: '',
        dateTo: '',
        format: 'csv',
      })
      showSuccess('Report request created successfully')
    },
    onError: (error) => {
      showError(`Failed to create report request: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['audit-reports', tenantId] })
  }

  const handleRowClick = async (report: AuditReport) => {
    setSelectedReport(report)
    setDetailLoading(true)
    setDrawerOpen(true)
    try {
      const fullReport = await getAuditReport(report.id, tenantId || '')
      setSelectedReport(fullReport)
    } catch (error) {
      showError(`Failed to load report details: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleRequestReport = () => {
    createReportMutation.mutate({
      reportType: requestForm.reportType,
      domain: requestForm.domain || undefined,
      dateFrom: requestForm.dateFrom || undefined,
      dateTo: requestForm.dateTo || undefined,
      format: requestForm.format,
    })
  }

  const handleDownload = async (report: AuditReport) => {
    try {
      if (!report.downloadUrl) {
        // Fetch the report to get the download URL
        const fullReport = await getAuditReport(report.id, tenantId || '')
        if (fullReport.downloadUrl) {
          window.open(fullReport.downloadUrl, '_blank')
          showSuccess('Report download started')
        } else {
          showError('Download URL not available for this report')
        }
      } else {
        window.open(report.downloadUrl, '_blank')
        showSuccess('Report download started')
      }
    } catch (error) {
      showError(`Failed to download report: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const columns: DataTableColumn<AuditReport>[] = [
    {
      id: 'id',
      label: 'Report ID',
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
      id: 'reportType',
      label: 'Report Type',
      accessor: (row) => (
        <Typography variant="body2">
          {row.reportType.replace(/_/g, ' ')}
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
            row.status === 'completed' ? 'success' :
            row.status === 'failed' ? 'error' :
            row.status === 'generating' ? 'warning' : 'default'
          }
        />
      ),
    },
    {
      id: 'requestedAt',
      label: 'Requested At',
      accessor: (row) => new Date(row.requestedAt).toLocaleString(),
    },
    {
      id: 'requestedBy',
      label: 'Requested By',
      accessor: (row) => row.requestedBy,
    },
    {
      id: 'completedAt',
      label: 'Completed',
      accessor: (row) => row.completedAt ? new Date(row.completedAt).toLocaleString() : '-',
    },
    {
      id: 'actions',
      label: 'Actions',
      accessor: (row) => (
        <Button
          size="small"
          variant="outlined"
          startIcon={<DownloadIcon />}
          onClick={() => handleDownload(row)}
          disabled={row.status !== 'completed' || !row.downloadUrl}
        >
          Download
        </Button>
      ),
    },
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to generate audit reports.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Audit Reports"
        subtitle="Generate and download audit reports"
        lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : undefined}
        onRefresh={handleRefresh}
        actions={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setRequestDialogOpen(true)}
          >
            Request Report
          </Button>
        }
      />

      <Paper sx={{ p: 2, mb: 3 }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Filter by Status</InputLabel>
          <Select
            value={statusFilter}
            label="Filter by Status"
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <MenuItem value="">All</MenuItem>
            <MenuItem value="queued">Queued</MenuItem>
            <MenuItem value="generating">Generating</MenuItem>
            <MenuItem value="completed">Completed</MenuItem>
            <MenuItem value="failed">Failed</MenuItem>
          </Select>
        </FormControl>
      </Paper>

      <DataTable
        columns={columns as DataTableColumn<Record<string, unknown>>[]}
        rows={(reportsData?.items || []) as Record<string, unknown>[]}
        loading={reportsLoading}
        page={page}
        pageSize={pageSize}
        totalCount={reportsData?.total || 0}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        emptyTitle="No reports yet"
        emptyMessage="No reports yet. Create a report request above."
      />

      {/* Detail Drawer */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedReport(null)
        }}
        PaperProps={{
          sx: { width: { xs: '100%', sm: 600 } },
        }}
      >
        <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6">Report Details</Typography>
            <IconButton onClick={() => {
              setDrawerOpen(false)
              setSelectedReport(null)
            }}>
              <CloseIcon />
            </IconButton>
          </Box>

          {detailLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <Alert severity="info">Loading report details...</Alert>
            </Box>
          ) : selectedReport ? (
            <>
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Report ID</Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {selectedReport.id}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Report Type</Typography>
                  <Typography variant="body2">{selectedReport.reportType.replace(/_/g, ' ')}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Status</Typography>
                  <Box>
                    <Chip
                      label={selectedReport.status}
                      size="small"
                      color={
                        selectedReport.status === 'completed' ? 'success' :
                        selectedReport.status === 'failed' ? 'error' :
                        selectedReport.status === 'generating' ? 'warning' : 'default'
                      }
                    />
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Requested By</Typography>
                  <Typography variant="body2">{selectedReport.requestedBy}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Requested At</Typography>
                  <Typography variant="body2">{new Date(selectedReport.requestedAt).toLocaleString()}</Typography>
                </Grid>
                {selectedReport.completedAt && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="text.secondary">Completed At</Typography>
                    <Typography variant="body2">{new Date(selectedReport.completedAt).toLocaleString()}</Typography>
                  </Grid>
                )}
                {selectedReport.errorReason && (
                  <Grid item xs={12}>
                    <Typography variant="caption" color="text.secondary">Error Reason</Typography>
                    <Typography variant="body2" color="error.main">{selectedReport.errorReason}</Typography>
                  </Grid>
                )}
              </Grid>

              {selectedReport.parameters && (
                <>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>Parameters</Typography>
                  <CodeViewer code={selectedReport.parameters} maxHeight={200} collapsible defaultCollapsed />
                </>
              )}

              <Divider sx={{ my: 3 }} />

              <Stack direction="row" spacing={2}>
                <Button
                  variant="contained"
                  startIcon={<DownloadIcon />}
                  onClick={() => handleDownload(selectedReport)}
                  disabled={selectedReport.status !== 'completed' || !selectedReport.downloadUrl}
                >
                  Download Report
                </Button>
              </Stack>
            </>
          ) : (
            <Alert severity="info">No report selected.</Alert>
          )}
        </Box>
      </Drawer>

      {/* Request Dialog */}
      <Dialog open={requestDialogOpen} onClose={() => setRequestDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Request Audit Report</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Report Type</InputLabel>
                <Select
                  value={requestForm.reportType}
                  label="Report Type"
                  onChange={(e) => setRequestForm({ ...requestForm, reportType: e.target.value })}
                >
                  <MenuItem value="exception_activity">Exception Activity</MenuItem>
                  <MenuItem value="tool_execution">Tool Execution</MenuItem>
                  <MenuItem value="policy_decisions">Policy Decisions</MenuItem>
                  <MenuItem value="config_changes">Config Changes</MenuItem>
                  <MenuItem value="sla_compliance">SLA Compliance</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Domain (optional)"
                value={requestForm.domain}
                onChange={(e) => setRequestForm({ ...requestForm, domain: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Date From"
                type="date"
                value={requestForm.dateFrom}
                onChange={(e) => setRequestForm({ ...requestForm, dateFrom: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Date To"
                type="date"
                value={requestForm.dateTo}
                onChange={(e) => setRequestForm({ ...requestForm, dateTo: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Format</InputLabel>
                <Select
                  value={requestForm.format}
                  label="Format"
                  onChange={(e) => setRequestForm({ ...requestForm, format: e.target.value as 'csv' | 'json' })}
                >
                  <MenuItem value="csv">CSV</MenuItem>
                  <MenuItem value="json">JSON</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRequestDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleRequestReport}
            disabled={createReportMutation.isPending}
          >
            Request Report
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

